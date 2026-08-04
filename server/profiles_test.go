package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

// 解析仓库内三个真实 profile 不得报错（两端共享合同）。
func TestLoadRealProfiles(t *testing.T) {
	profiles, err := loadProfiles("../profiles")
	if err != nil {
		t.Fatalf("loadProfiles: %v", err)
	}
	want := []string{"s1_chat", "s2_coding_agent", "s3_multimodal"}
	// >= 而非 ==：T47 批②新增 s4_throughput（additive、非 REQUIRED_IDS 成员）后目录里
	// 会有第 4 个 profile；本测的真实意图是"三个必需场景都解析正确"，不是"目录里恰好
	// 三个文件"，用严格相等会让每次新增可选 profile 都得回来改这个数字（D-321/D-322
	// 同族教训：断言该钉住的不变量，别钉住会随功能增长而漂移的计数）。
	if len(profiles) < len(want) {
		t.Fatalf("got %d profiles, want at least %d", len(profiles), len(want))
	}
	for _, id := range want {
		p, ok := profiles[id]
		if !ok {
			t.Fatalf("missing profile %s", id)
		}
		if p.Version == "" || p.KpiSet == "" || len(p.Phases) == 0 {
			t.Fatalf("profile %s incompletely parsed: %+v", id, p)
		}
	}
	// s2 有两个 token_stream phase，且 burst 参数解析完整。
	s2 := profiles["s2_coding_agent"]
	ph0, err := s2.tokenStreamPhase(0)
	if err != nil {
		t.Fatal(err)
	}
	if ph0.Tokens != 300 || ph0.Seed != 2001 || ph0.Burst == nil || ph0.Burst.ClusterTps != 100 {
		t.Fatalf("s2 stream phase 0 wrong: %+v", ph0)
	}
	if len(ph0.Burst.PauseMs) != 2 || ph0.Burst.PauseMs[0] != 300 || ph0.Burst.PauseMs[1] != 800 {
		t.Fatalf("s2 burst pause_ms wrong: %+v", ph0.Burst.PauseMs)
	}
	ph1, err := s2.tokenStreamPhase(1)
	if err != nil {
		t.Fatal(err)
	}
	if ph1.Tokens != 800 || ph1.Seed != 2002 {
		t.Fatalf("s2 stream phase 1 wrong: %+v", ph1)
	}
	if _, err := s2.tokenStreamPhase(2); err == nil {
		t.Fatal("expected error for out-of-range token_stream index")
	}
}

// T47 批②（D-468/D-469）：s4_throughput 的两个新 phase 类型解析出 WindowMs，
// 与 Kotlin 侧 ProfileAndReportTest 对称覆盖（两端共享合同，各自独立核实解析正确）。
func TestLoadS4ThroughputAdaptiveWindowPhases(t *testing.T) {
	profiles, err := loadProfiles("../profiles")
	if err != nil {
		t.Fatalf("loadProfiles: %v", err)
	}
	s4, ok := profiles["s4_throughput"]
	if !ok {
		t.Fatal("s4_throughput profile not found in ../profiles")
	}
	var down, up *Phase
	for i := range s4.Phases {
		switch s4.Phases[i].Type {
		case "adaptive_download_window":
			down = &s4.Phases[i]
		case "adaptive_upload_window":
			up = &s4.Phases[i]
		}
	}
	if down == nil || up == nil {
		t.Fatalf("s4_throughput missing adaptive window phases: %+v", s4.Phases)
	}
	if down.WindowMs != 4000 || down.Bytes != 536870912 {
		t.Fatalf("adaptive_download_window wrong: %+v", down)
	}
	if up.WindowMs != 4000 || up.Bytes != 50331648 {
		t.Fatalf("adaptive_upload_window wrong: %+v", up)
	}
}

func TestProfilesEndpoint(t *testing.T) {
	profiles, err := loadProfiles("../profiles")
	if err != nil {
		t.Fatalf("loadProfiles: %v", err)
	}
	a := &app{profiles: profiles, dataDir: t.TempDir()}
	srv := httptest.NewServer(a.routes())
	defer srv.Close()

	resp, err := http.Get(srv.URL + "/api/v1/profiles")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("status %d", resp.StatusCode)
	}
	if got := resp.Header.Get("X-Aneb-Server"); got != serverVersion {
		t.Fatalf("X-Aneb-Server = %q, want %q", got, serverVersion)
	}
	var body struct {
		ServerVersion string     `json:"server_version"`
		Profiles      []*Profile `json:"profiles"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
		t.Fatalf("decode: %v", err)
	}
	// >= 3 而非 == 3，理由同 TestLoadRealProfiles（T47 批②新增 s4_throughput 后目录里
	// 有第 4 个 additive profile，本测钉住的是"必需三场景都下发"，不是文件总数）。
	if len(body.Profiles) < 3 {
		t.Fatalf("got %d profiles, want at least 3", len(body.Profiles))
	}
	byID := make(map[string]*Profile, len(body.Profiles))
	for _, p := range body.Profiles {
		if p.ProfileID == "" || p.Version == "" {
			t.Fatalf("profile missing id/version: %+v", p)
		}
		byID[p.ProfileID] = p
	}
	for _, id := range []string{"s1_chat", "s2_coding_agent", "s3_multimodal"} {
		if _, ok := byID[id]; !ok {
			t.Fatalf("required profile %s missing from /api/v1/profiles response", id)
		}
	}
}
