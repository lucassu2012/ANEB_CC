package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// ---- 注册表完整性 + 诚实 provenance（§3.3） ----

// 内置通用包必须显式 UNCALIBRATED：Calibrated=false、Note 非空、Provider 空，
// median/sigma 镜像历史全局常数（单一事实源）。stamp = id@version。
func TestBehaviorModelGenericIsHonestlyUncalibrated(t *testing.T) {
	m, err := lookupBehaviorModel(genericBehaviorModelID)
	if err != nil || m == nil {
		t.Fatalf("generic pack lookup: m=%v err=%v", m, err)
	}
	if m.Provenance.Calibrated {
		t.Fatal("generic pack must NOT claim calibration (red-line §3.4)")
	}
	if strings.TrimSpace(m.Provenance.Note) == "" {
		t.Fatal("uncalibrated pack must carry an explanatory Note")
	}
	if m.Provider != "" {
		t.Fatalf("generic pack Provider = %q, want empty", m.Provider)
	}
	if m.Median != defaultStreamMedian || m.Sigma != defaultStreamSigma {
		t.Fatalf("generic pack median/sigma = %v/%v, want %v/%v (single source of truth)",
			m.Median, m.Sigma, defaultStreamMedian, defaultStreamSigma)
	}
	if got := m.stamp(); got != genericBehaviorModelID+"@v0" {
		t.Fatalf("stamp = %q, want %s@v0", got, genericBehaviorModelID)
	}
}

// lookup：空 id → (nil,nil)（未引用，行为不变）；未知 id → error（坏契约不静默兜底）。
func TestLookupBehaviorModel(t *testing.T) {
	if m, err := lookupBehaviorModel(""); m != nil || err != nil {
		t.Fatalf("empty id → (%v,%v), want (nil,nil)", m, err)
	}
	if _, err := lookupBehaviorModel("does-not-exist"); err == nil {
		t.Fatal("unknown id must error")
	}
}

// nil stamp/receiver 安全：无 pack 时 applyDefaults 是 no-op、stamp 空。
func TestBehaviorModelNilIsNoOp(t *testing.T) {
	var m *BehaviorModel
	if m.stamp() != "" {
		t.Fatal("nil pack stamp must be empty")
	}
	params := StreamParams{Median: 120, Sigma: 0.6}
	m.applyDefaults(&params, false)
	if params.Median != 120 || params.Sigma != 0.6 || params.TtftInjectUs != 0 ||
		params.TokensPerFrame != 0 || len(params.RateSchedule) != 0 || params.BehaviorModelStamp != "" {
		t.Fatalf("nil pack must not mutate params: %+v", params)
	}
}

// ---- 解析分层（INV-3：phase 已声明者胜、其余由 pack 补齐） ----

func TestBehaviorModelFillsUnsetKnobs(t *testing.T) {
	pack := &BehaviorModel{
		ID: "x", Version: "vT",
		TtftInjectUs:   7_000,
		TokensPerFrame: 4,
		RateSchedule:   []RatePoint{{AtFrac: 0, Tps: 60}, {AtFrac: 1, Tps: 20}},
		Median:         200, Sigma: 0.9,
	}
	// phase 未声明任何模型旋钮（全零/空、且无 token_bytes）→ pack 全量补齐。
	params := StreamParams{Tokens: 10, RateTps: 40}
	pack.applyDefaults(&params, false)
	if params.TtftInjectUs != 7_000 || params.TokensPerFrame != 4 {
		t.Fatalf("pack ttft/frame not filled: %+v", params)
	}
	if len(params.RateSchedule) != 2 {
		t.Fatalf("pack rate_schedule not filled: %+v", params.RateSchedule)
	}
	if params.Median != 200 || params.Sigma != 0.9 {
		t.Fatalf("pack byte model not filled: median=%v sigma=%v", params.Median, params.Sigma)
	}
	if params.BehaviorModelStamp != "x@vT" {
		t.Fatalf("stamp = %q, want x@vT", params.BehaviorModelStamp)
	}
}

func TestBehaviorModelPhaseOverridesWin(t *testing.T) {
	pack := &BehaviorModel{
		ID: "x", Version: "vT",
		TtftInjectUs:   7_000,
		TokensPerFrame: 4,
		RateSchedule:   []RatePoint{{AtFrac: 0, Tps: 60}},
		Median:         200, Sigma: 0.9,
	}
	// phase 已声明这些旋钮（含 token_bytes）→ pack 不得覆盖。
	params := StreamParams{
		Tokens: 10, RateTps: 40,
		TtftInjectUs:   3_000,
		TokensPerFrame: 2,
		RateSchedule:   []RatePoint{{AtFrac: 0, Tps: 99}},
		Median:         120, Sigma: 0.6,
	}
	pack.applyDefaults(&params, true) // tokenBytesSet=true：字节模型归 phase
	if params.TtftInjectUs != 3_000 {
		t.Fatalf("phase ttft overridden by pack: %d", params.TtftInjectUs)
	}
	if params.TokensPerFrame != 2 {
		t.Fatalf("phase tokens_per_frame overridden: %d", params.TokensPerFrame)
	}
	if len(params.RateSchedule) != 1 || params.RateSchedule[0].Tps != 99 {
		t.Fatalf("phase rate_schedule overridden: %+v", params.RateSchedule)
	}
	if params.Median != 120 || params.Sigma != 0.6 {
		t.Fatalf("phase token_bytes overridden by pack: median=%v sigma=%v", params.Median, params.Sigma)
	}
}

// ---- 端到端：generic 包是忠实 no-op 默认 + 加溯源印（零回归） ----

type preludeBM struct {
	SrvTsUs       int64  `json:"srv_ts_us"`
	TtftInjectUs  int64  `json:"ttft_inject_us"`
	BehaviorModel string `json:"behavior_model"`
}

func parsePreludeBM(t *testing.T, frames []sseFrame) preludeBM {
	t.Helper()
	var p preludeBM
	if err := json.Unmarshal([]byte(strings.TrimPrefix(frames[0].comment, "prelude ")), &p); err != nil {
		t.Fatalf("prelude JSON: %v", err)
	}
	return p
}

// relToken 是一个 token 的**确定性**部分：相对流起点的计划偏移 + payload。
// （sched_us 是绝对进程锚点时戳、pre_flush_us 是实测 flush 时戳，均随 run 变化，
// 不可直接逐帧比较；须先减 stream_start_us 归一。）
type relToken struct {
	offUs   int64
	payload string
}

func relTokens(t *testing.T, frames []sseFrame) []relToken {
	t.Helper()
	var sum summaryData
	if err := json.Unmarshal([]byte(frames[len(frames)-1].data), &sum); err != nil {
		t.Fatalf("summary JSON: %v", err)
	}
	var out []relToken
	for _, f := range frames {
		if f.event != "token" {
			continue
		}
		var td tokenData
		if err := json.Unmarshal([]byte(f.data), &td); err != nil {
			t.Fatalf("token JSON: %v", err)
		}
		out = append(out, relToken{offUs: td.SchedUs - sum.StreamStartUs, payload: td.Payload})
	}
	return out
}

// 引用 generic 包：prelude 带 behavior_model 印；token 时刻表/大小与不引用时**逐帧一致**
// （generic 镜像默认，故是忠实 no-op；证明解析路径运行且不扰动确定性）。
func TestStreamGenericPackStampAndIdenticalSchedule(t *testing.T) {
	base := &Profile{ProfileID: "bm_base", Version: "test@1",
		Phases: []Phase{{Type: "token_stream", Tokens: 8, RateTps: 2000, Seed: 42}}}
	withPack := &Profile{ProfileID: "bm_pack", Version: "test@1",
		Phases: []Phase{{Type: "token_stream", Tokens: 8, RateTps: 2000, Seed: 42,
			BehaviorModelID: genericBehaviorModelID}}}
	a := &app{profiles: map[string]*Profile{"bm_base": base, "bm_pack": withPack}, dataDir: t.TempDir()}
	srv := httptest.NewServer(a.routes())
	defer srv.Close()

	baseFrames := fetchStream(t, srv.URL+"/api/v1/stream?profile=bm_base")
	packFrames := fetchStream(t, srv.URL+"/api/v1/stream?profile=bm_pack")

	// baseline prelude 无 behavior_model 键（未引用 pack）。
	if s := parsePreludeBM(t, baseFrames).BehaviorModel; s != "" {
		t.Fatalf("baseline prelude behavior_model = %q, want empty", s)
	}
	// pack prelude 带溯源印。
	if s := parsePreludeBM(t, packFrames).BehaviorModel; s != genericBehaviorModelID+"@v0" {
		t.Fatalf("pack prelude behavior_model = %q, want %s@v0", s, genericBehaviorModelID)
	}
	// 相对时刻表 + payload 逐一相等（generic 包不扰动确定性时刻表/大小序列）。
	bt, pt := relTokens(t, baseFrames), relTokens(t, packFrames)
	if len(bt) != len(pt) || len(bt) != 8 {
		t.Fatalf("token count base=%d pack=%d, want 8", len(bt), len(pt))
	}
	for i := range bt {
		if bt[i] != pt[i] {
			t.Fatalf("token %d differs with generic pack:\n base=%+v\n pack=%+v", i, bt[i], pt[i])
		}
	}
}

// 引用带非默认注入的 pack：端到端确实生效（首 token 右移 pack 的 dwell）——证明
// streamParamsFromRequest→applyDefaults→GenerateTokens 全链贯通。临时注册、用后即删。
func TestStreamPackInjectPropagatesEndToEnd(t *testing.T) {
	const id = "test-inject-pack"
	behaviorModels[id] = &BehaviorModel{ID: id, Version: "vT", TtftInjectUs: 12_345,
		Provenance: Provenance{Calibrated: false, Note: "test-only"}}
	t.Cleanup(func() { delete(behaviorModels, id) })

	prof := &Profile{ProfileID: "bm_inj", Version: "test@1",
		Phases: []Phase{{Type: "token_stream", Tokens: 5, RateTps: 2000, Seed: 1, BehaviorModelID: id}}}
	a := &app{profiles: map[string]*Profile{"bm_inj": prof}, dataDir: t.TempDir()}
	srv := httptest.NewServer(a.routes())
	defer srv.Close()

	frames := fetchStream(t, srv.URL+"/api/v1/stream?profile=bm_inj")
	pre := parsePreludeBM(t, frames)
	if pre.BehaviorModel != id+"@vT" {
		t.Fatalf("prelude behavior_model = %q, want %s@vT", pre.BehaviorModel, id)
	}
	if pre.TtftInjectUs != 12_345 {
		t.Fatalf("prelude ttft_inject_us = %d, want 12345 (from pack)", pre.TtftInjectUs)
	}
	var first tokenData
	if err := json.Unmarshal([]byte(frames[1].data), &first); err != nil {
		t.Fatalf("first token JSON: %v", err)
	}
	var sum summaryData
	if err := json.Unmarshal([]byte(frames[len(frames)-1].data), &sum); err != nil {
		t.Fatalf("summary JSON: %v", err)
	}
	if got := first.SchedUs - sum.StreamStartUs; got != 12_345 {
		t.Fatalf("first token dwell = %d, want 12345 (pack inject applied)", got)
	}
}

// profile 引用未知 pack → 400（坏契约显式失败，不静默）。
func TestStreamUnknownPackRejected(t *testing.T) {
	prof := &Profile{ProfileID: "bm_bad", Version: "test@1",
		Phases: []Phase{{Type: "token_stream", Tokens: 5, RateTps: 2000, Seed: 1,
			BehaviorModelID: "no-such-pack"}}}
	a := &app{profiles: map[string]*Profile{"bm_bad": prof}, dataDir: t.TempDir()}
	srv := httptest.NewServer(a.routes())
	defer srv.Close()

	resp, err := http.Get(srv.URL + "/api/v1/stream?profile=bm_bad")
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("unknown pack status = %d, want 400", resp.StatusCode)
	}
}

// /profiles 透出 behavior_models（含 provenance），供客户端盖入结果溯源。
func TestProfilesEndpointExposesBehaviorModels(t *testing.T) {
	a := &app{profiles: map[string]*Profile{}, dataDir: t.TempDir()}
	srv := httptest.NewServer(a.routes())
	defer srv.Close()

	resp, err := http.Get(srv.URL + "/api/v1/profiles")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	var body struct {
		BehaviorModels []BehaviorModel `json:"behavior_models"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
		t.Fatalf("decode /profiles: %v", err)
	}
	if len(body.BehaviorModels) == 0 {
		t.Fatal("/profiles must expose behavior_models")
	}
	var found bool
	for _, m := range body.BehaviorModels {
		if m.ID == genericBehaviorModelID {
			found = true
			if m.Provenance.Calibrated {
				t.Fatal("exposed generic pack must report calibrated=false")
			}
		}
	}
	if !found {
		t.Fatalf("generic pack not exposed in /profiles")
	}
}
