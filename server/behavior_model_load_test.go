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
}

// ---- 端到端回路：mock OpenAI 端点 → 采集解析 → 拟合 → 包文件 → 服务器加载 → /stream 重放 ----
//
// 这是 §3.3 标定管线的贯通性证明：llmcap（ParseOpenAIStream 同源）采到的 trace 经
// calibrate（Calibrate 同源）拟合，产物无需人工编辑即被 aneb-server 加载并驱动
// token 流重放（prelude 溯源印 + TTFT 注入生效）。
func TestCalibrationPipelineEndToEnd(t *testing.T) {
	// 1) mock OpenAI 兼容端点：role 帧 + 60 content 帧 + finish + [DONE]（无 sleep——
	//    贯通性测试不依赖真实节奏；到达全聚一簇正好覆盖 tokens_per_frame 上限路径）。
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
