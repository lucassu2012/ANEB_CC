package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"

	"aneb-server/internal/behaviorspec"
)

// writePack 把 Model marshal 成 dir 下的 JSON 包文件（schema=behaviorspec 单源）。
func writePack(t *testing.T, dir string, m *behaviorspec.Model) string {
	t.Helper()
	data, err := json.MarshalIndent(m, "", "  ")
	if err != nil {
		t.Fatal(err)
	}
	p := filepath.Join(dir, m.ID+".json")
	if err := os.WriteFile(p, data, 0o644); err != nil {
		t.Fatal(err)
	}
	return p
}

func validPack(id string) *behaviorspec.Model {
	return &behaviorspec.Model{
		ID: id, Version: "v1", Provider: "test",
		TtftInjectUs: 5000,
		Provenance:   behaviorspec.Provenance{Calibrated: true, Source: "test", Note: "测试包"},
	}
}

// 目录加载：合法包并入注册表、lookup 可得、/profiles 透出。
func TestLoadBehaviorModelsFromDir(t *testing.T) {
	dir := t.TempDir()
	writePack(t, dir, validPack("dir-pack"))
	if err := loadBehaviorModels(dir); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { delete(behaviorModels, "dir-pack") })

	m, err := lookupBehaviorModel("dir-pack")
	if err != nil || m == nil || !m.Provenance.Calibrated || m.TtftInjectUs != 5000 {
		t.Fatalf("loaded pack wrong: %+v err=%v", m, err)
	}
	var found bool
	for _, lm := range behaviorModelList() {
		if lm.ID == "dir-pack" {
			found = true
		}
	}
	if !found {
		t.Fatal("loaded pack must appear in behaviorModelList (→ /profiles)")
	}
}

// 校验拒绝：Note 空 / id 带 @ / ttft 超界 / rate_schedule 非法 / 与内置重复 / 坏 JSON。
func TestLoadBehaviorModelsRejectsInvalid(t *testing.T) {
	bad := []struct {
		name string
		mut  func(*behaviorspec.Model)
	}{
		{"empty note", func(m *behaviorspec.Model) { m.Provenance.Note = " " }},
		{"id with @", func(m *behaviorspec.Model) { m.ID = "a@b" }},
		{"version with @", func(m *behaviorspec.Model) { m.Version = "v1@rc" }},
		{"ttft over cap", func(m *behaviorspec.Model) { m.TtftInjectUs = behaviorspec.MaxTtftInjectUs + 1 }},
		{"tpf over cap", func(m *behaviorspec.Model) { m.TokensPerFrame = behaviorspec.MaxTokensPerFrame + 1 }},
		{"bad schedule", func(m *behaviorspec.Model) { m.RateSchedule = []RatePoint{{AtFrac: 2, Tps: 40}} }},
		{"bad histogram", func(m *behaviorspec.Model) { m.SizeHistogram = []SizeBin{{Size: 5, Weight: 1}} }},
		{"negative sigma", func(m *behaviorspec.Model) { m.Sigma = -1 }},
		{"duplicate of builtin", func(m *behaviorspec.Model) { m.ID = genericBehaviorModelID }},
	}
	for _, c := range bad {
		dir := t.TempDir()
		m := validPack("bad-pack")
		c.mut(m)
		writePack(t, dir, m)
		if err := loadBehaviorModels(dir); err == nil {
			delete(behaviorModels, m.ID)
			t.Fatalf("%s: expected load error", c.name)
		}
	}
	// 坏 JSON 文件
	dir := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir, "junk.json"), []byte("{nope"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := loadBehaviorModels(dir); err == nil {
		t.Fatal("malformed JSON must error")
	}
	// 未知字段（旋钮名拼错）→ DisallowUnknownFields 报错，不静默丢弃成缺省。
	dir2 := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir2, "typo.json"),
		[]byte(`{"id":"typo","version":"v1","rate_shedule":[],"provenance":{"note":"x"}}`), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := loadBehaviorModels(dir2); err == nil {
		delete(behaviorModels, "typo")
		t.Fatal("misspelled knob (unknown field) must error")
	}
}

// 契约(1)：calibrate 的**含 rate_schedule / 合并直方图**产物必须免编辑通过服务器加载
// ——手写断言（behaviorspec 包内）与服务器校验器（主包）分属两包，正是 INV-3 要防的漂移。
// 直接把 Calibrate 输出喂 loadBehaviorModels，跨包钉死。
func TestCalibrateOutputsLoadServerSide(t *testing.T) {
	mk := func(n int, at func(int) int64, wb func(int) int) behaviorspec.Trace {
		tr := behaviorspec.Trace{Meta: behaviorspec.TraceMeta{Endpoint: "http://e", Model: "m", CapturedAt: "2026-07-17T00:00:00Z"}}
		for i := 0; i < n; i++ {
			tr.Events = append(tr.Events, behaviorspec.TraceEvent{Index: i, ArrivalUs: at(i), WireBytes: wb(i), ContentBytes: 3})
		}
		return tr
	}
	// (a) 减速流 → 含 rate_schedule；(b) 宽字节分布 → 合并直方图。
	decay := mk(101, func(i int) int64 {
		if i <= 50 {
			return 200_000 + int64(i)*10_000
		}
		return 700_000 + int64(i-50)*20_000
	}, func(int) int { return 120 })
	wide := mk(120, func(i int) int64 { return int64(i) * 25_000 }, func(i int) int { return 40 + i })

	for name, tr := range map[string]behaviorspec.Trace{"schedule": decay, "merged-hist": wide} {
		m, _, err := behaviorspec.Calibrate([]behaviorspec.Trace{tr}, behaviorspec.FitOptions{ID: "srv-" + name, Version: "v1"})
		if err != nil {
			t.Fatalf("%s calibrate: %v", name, err)
		}
		dir := t.TempDir()
		writePack(t, dir, m)
		if err := loadBehaviorModels(dir); err != nil {
			t.Fatalf("%s: calibrate output must load server-side unedited: %v", name, err)
		}
		delete(behaviorModels, m.ID)
	}
}

// HIGH：burst phase 引用含 rate_schedule 的包 → /stream 不得 400（包给 burst 补曲线是无效配置）。
func TestBurstPhaseWithSchedulePackDoesNotBreakStream(t *testing.T) {
	const id = "burst-sched-pack"
	behaviorModels[id] = &behaviorspec.Model{
		ID: id, Version: "v1",
		RateSchedule: []RatePoint{{AtFrac: 0, Tps: 100}, {AtFrac: 1, Tps: 40}},
		TtftInjectUs: 3000,
		Provenance:   behaviorspec.Provenance{Calibrated: true, Note: "test"},
	}
	t.Cleanup(func() { delete(behaviorModels, id) })

	prof := &Profile{ProfileID: "burst_prof", Version: "test@1",
		Phases: []Phase{{Type: "token_stream", Tokens: 12, Seed: 3,
			Burst:           &Burst{ClusterTps: 100, PauseMs: []int{5, 10}, ClusterGeomP: 0.4},
			BehaviorModelID: id}}}
	a := &app{profiles: map[string]*Profile{"burst_prof": prof}, dataDir: t.TempDir()}
	srv := httptest.NewServer(a.routes())
	defer srv.Close()

	// 400 会让 fetchStream 直接 Fatal——能取到帧即证明未被 rate_schedule 校验拒绝。
	frames := fetchStream(t, srv.URL+"/api/v1/stream?profile=burst_prof")
	pre := parsePreludeBM(t, frames)
	if pre.BehaviorModel != id+"@v1" {
		t.Fatalf("stamp = %q", pre.BehaviorModel)
	}
	// burst phase 的 TTFT 注入仍生效（首 token 右移 3000）；rate_schedule 被跳过不报错。
	if pre.TtftInjectUs != 3000 {
		t.Fatalf("burst phase ttft = %d, want 3000 (pack applied)", pre.TtftInjectUs)
	}
}

// ---- 端到端回路：mock OpenAI 端点 → 采集解析 → 拟合 → 包文件 → 服务器加载 → /stream 重放 ----
//
// 这是 §3.3 标定管线的贯通性证明：llmcap（ParseOpenAIStream 同源）采到的 trace 经
// calibrate（Calibrate 同源）拟合，产物无需人工编辑即被 aneb-server 加载并驱动
// token 流重放（prelude 溯源印 + TTFT 注入生效）。
func TestCalibrationPipelineEndToEnd(t *testing.T) {
	// 1) mock OpenAI 兼容端点：role 帧 + 60 content 帧 + finish + [DONE]（无 sleep——
	//    贯通性测试只证明「采集→拟合→加载→重放」全链贯通，不校验拟合保真度；
	//    保真度/边界路径由 behaviorspec/*_test.go + TestCalibrateOutputsLoadServerSide 确定性覆盖）。
	mock := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		f := w.(http.Flusher)
		w.Header().Set("Content-Type", "text/event-stream")
		fmt.Fprint(w, `data: {"choices":[{"delta":{"role":"assistant","content":""},"finish_reason":null}]}`+"\n\n")
		for i := 0; i < 60; i++ {
			fmt.Fprintf(w, `data: {"choices":[{"delta":{"content":"词%02d的内容片段"},"finish_reason":null}]}`+"\n\n", i)
		}
		fmt.Fprint(w, `data: {"choices":[{"delta":{},"finish_reason":"stop"}]}`+"\n\ndata: [DONE]\n\n")
		f.Flush()
	}))
	defer mock.Close()

	// 2) 采集（llmcap 的解析路径，同一函数）。
	resp, err := http.Get(mock.URL)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	anchor := time.Now()
	events, finish, skipped, err := behaviorspec.ParseOpenAIStream(resp.Body,
		func() int64 { return time.Since(anchor).Microseconds() })
	if err != nil || skipped != 0 || finish != "stop" || len(events) != 60 {
		t.Fatalf("capture: events=%d finish=%q skipped=%d err=%v", len(events), finish, skipped, err)
	}

	// 3) 拟合（calibrate 的核心路径，同一函数）→ 包文件。
	trace := behaviorspec.Trace{
		Meta: behaviorspec.TraceMeta{Endpoint: mock.URL, Model: "mock-llm",
			CapturedAt: "2026-07-17T00:00:00Z", Tool: "test"},
		Events: events,
	}
	model, report, err := behaviorspec.Calibrate([]behaviorspec.Trace{trace},
		behaviorspec.FitOptions{ID: "e2e-mock", Version: "v1", Provider: "mock"})
	if err != nil {
		t.Fatalf("calibrate: %v (report=%+v)", err, report)
	}
	model.Provenance.Source = behaviorspec.SourceSummary([]behaviorspec.Trace{trace}, []string{"run1.jsonl"})
	dir := t.TempDir()
	writePack(t, dir, model)

	// 4) 服务器加载（无需人工编辑——calibrate 产物必须直接过校验）。
	if err := loadBehaviorModels(dir); err != nil {
		t.Fatalf("server must load calibrate output as-is: %v", err)
	}
	t.Cleanup(func() { delete(behaviorModels, "e2e-mock") })

	// 5) profile 引用该包 → /stream 重放：prelude 带溯源印、TTFT 注入=拟合值。
	prof := &Profile{ProfileID: "e2e_prof", Version: "test@1",
		Phases: []Phase{{Type: "token_stream", Tokens: 5, RateTps: 2000, Seed: 7, BehaviorModelID: "e2e-mock"}}}
	a := &app{profiles: map[string]*Profile{"e2e_prof": prof}, dataDir: t.TempDir()}
	srv := httptest.NewServer(a.routes())
	defer srv.Close()

	frames := fetchStream(t, srv.URL+"/api/v1/stream?profile=e2e_prof")
	pre := parsePreludeBM(t, frames)
	if pre.BehaviorModel != "e2e-mock@v1" {
		t.Fatalf("prelude behavior_model = %q, want e2e-mock@v1", pre.BehaviorModel)
	}
	if pre.TtftInjectUs != model.TtftInjectUs {
		t.Fatalf("prelude ttft = %d, want fitted %d", pre.TtftInjectUs, model.TtftInjectUs)
	}
	var first tokenData
	if err := json.Unmarshal([]byte(frames[1].data), &first); err != nil {
		t.Fatal(err)
	}
	var sum summaryData
	if err := json.Unmarshal([]byte(frames[len(frames)-1].data), &sum); err != nil {
		t.Fatal(err)
	}
	if got := first.SchedUs - sum.StreamStartUs; got != model.TtftInjectUs {
		t.Fatalf("first token dwell = %d, want fitted %d", got, model.TtftInjectUs)
	}
}
