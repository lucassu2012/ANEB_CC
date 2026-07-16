package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// TokenBytes 描述单 token 事件 payload 字节数分布：默认对数正态(median,sigma)；
// 若 Histogram 非空则改用每模型经验直方图（§3.2，取代全局 median=120/sigma=0.6）。
type TokenBytes struct {
	Dist      string    `json:"dist"`
	Median    float64   `json:"median"`
	Sigma     float64   `json:"sigma"`
	Histogram []SizeBin `json:"histogram,omitempty"`
}

// Burst 描述突发簇节奏（S2 编码 Agent 流）。
type Burst struct {
	ClusterTps   float64 `json:"cluster_tps"`
	PauseMs      []int   `json:"pause_ms"` // [min, max]
	ClusterGeomP float64 `json:"cluster_geom_p"`
}

// Phase 是 profile 中一个阶段的联合体，字段按 type 选用。
type Phase struct {
	Type string `json:"type"`

	// clock_sync
	Samples int `json:"samples,omitempty"`

	// upload_burst
	Bytes   int64 `json:"bytes,omitempty"`
	ChunkKB int   `json:"chunk_kb,omitempty"`

	// think_pause
	DurationMs int `json:"duration_ms,omitempty"`

	// token_stream
	Tokens     int         `json:"tokens,omitempty"`
	RateTps    float64     `json:"rate_tps,omitempty"`
	TokenBytes *TokenBytes `json:"token_bytes,omitempty"`
	Burst      *Burst      `json:"burst,omitempty"`
	Seed       int64       `json:"seed,omitempty"`
	// TtftInjectUs：首 token 前注入的确定性 TTFT 驻留（模拟 AI 排队/prefill/think，§3.2/§3.4）；
	// 服务端 prelude 透出供 APP 从 T1 减去。省略=0=无注入（行为不变）。
	TtftInjectUs int64 `json:"ttft_inject_us,omitempty"`
	// RateSchedule：非平稳解码 TPS 曲线（上下文衰减，§3.2）；省略=常速 rate_tps（行为不变）。仅均匀模式生效。
	RateSchedule []RatePoint `json:"rate_schedule,omitempty"`
	// TokensPerFrame：每个 SSE 帧合并的 token 数（frame-batching，§3.2）；省略/0/1=每 token 一帧（行为不变）。
	TokensPerFrame int `json:"tokens_per_frame,omitempty"`
	// ThinkInjections：流内 think 驻留（§3.2，reasoning 模型中途思考）；省略=无（行为不变）。
	ThinkInjections []ThinkInjection `json:"think_injections,omitempty"`

	// tool_loop
	Rounds       int   `json:"rounds,omitempty"`
	UpBytes      int64 `json:"up_bytes,omitempty"`
	DownBytes    int64 `json:"down_bytes,omitempty"`
	ServerProcMs int   `json:"server_proc_ms,omitempty"`

	// artifact_stream（§3.1，复用 Bytes/ChunkKB/Seed）：下行渐进生成节奏与类别。
	CadenceBps    int64  `json:"cadence_bps,omitempty"`
	ArtifactClass string `json:"artifact_class,omitempty"`

	// BehaviorModelID 引用一个版本化行为模型参数包（§3.3，behavior_model.go 注册表）。
	// 声明后，该 token_stream phase 未显式给出的 §3.2 模型旋钮（ttft/tokens_per_frame/
	// rate_schedule/token 字节）由 pack 默认补齐；phase 已声明者恒胜（INV-3 分层）。
	// 省略=不引用 pack（行为不变）。仅 token_stream 相位有意义。
	BehaviorModelID string `json:"behavior_model_id,omitempty"`
}

// Profile 是版本化场景定义（发布即冻结，修改必须升版本号）。
type Profile struct {
	ProfileID    string  `json:"profile_id"`
	Version      string  `json:"version"`
	KpiSet       string  `json:"kpi_set"`
	Description  string  `json:"description,omitempty"`
	EstDurationS float64 `json:"est_duration_s,omitempty"`
	Phases       []Phase `json:"phases"`
}

// firstTokenStream 返回第 idx 个 token_stream phase（idx 从 0 计，只数 token_stream）。
func (p *Profile) tokenStreamPhase(idx int) (*Phase, error) {
	n := 0
	for i := range p.Phases {
		if p.Phases[i].Type == "token_stream" {
			if n == idx {
				return &p.Phases[i], nil
			}
			n++
		}
	}
	return nil, fmt.Errorf("profile %s: token_stream phase index %d not found (has %d)", p.ProfileID, idx, n)
}

// downloadBurstPhase 返回第 idx 个 download_burst phase（idx 从 0 计，只数 download_burst）。
// download_burst 声明 TK-5 下行大对象拉取（PROFILE_FRAMEWORK §2.4/§3.1，接 /download 供 D1）。
func (p *Profile) downloadBurstPhase(idx int) (*Phase, error) {
	n := 0
	for i := range p.Phases {
		if p.Phases[i].Type == "download_burst" {
			if n == idx {
				return &p.Phases[i], nil
			}
			n++
		}
	}
	return nil, fmt.Errorf("profile %s: download_burst phase index %d not found (has %d)", p.ProfileID, idx, n)
}

// artifactStreamPhase 返回第 idx 个 artifact_stream phase（idx 从 0 计，只数 artifact_stream）。
// artifact_stream 声明下行渐进生成内容（PROFILE_FRAMEWORK §3.1，接 /artifact_stream）。
func (p *Profile) artifactStreamPhase(idx int) (*Phase, error) {
	n := 0
	for i := range p.Phases {
		if p.Phases[i].Type == "artifact_stream" {
			if n == idx {
				return &p.Phases[i], nil
			}
			n++
		}
	}
	return nil, fmt.Errorf("profile %s: artifact_stream phase index %d not found (has %d)", p.ProfileID, idx, n)
}

// loadProfiles 读取目录下全部 *.json 并解析为 Profile。
// 解析失败任一文件即整体报错（profile 是两端共享合同，不允许静默跳过）。
func loadProfiles(dir string) (map[string]*Profile, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, fmt.Errorf("read profiles dir %s: %w", dir, err)
	}
	profiles := make(map[string]*Profile)
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(strings.ToLower(e.Name()), ".json") {
			continue
		}
		path := filepath.Join(dir, e.Name())
		data, err := os.ReadFile(path)
		if err != nil {
			return nil, fmt.Errorf("read %s: %w", path, err)
		}
		var p Profile
		if err := json.Unmarshal(data, &p); err != nil {
			return nil, fmt.Errorf("parse %s: %w", path, err)
		}
		if p.ProfileID == "" || p.Version == "" {
			return nil, fmt.Errorf("parse %s: missing profile_id or version", path)
		}
		if _, dup := profiles[p.ProfileID]; dup {
			return nil, fmt.Errorf("duplicate profile_id %q in %s", p.ProfileID, path)
		}
		profiles[p.ProfileID] = &p
	}
	return profiles, nil
}

// handleProfiles GET /api/v1/profiles：下发全部 profile（含 profile_id/version）。
func (a *app) handleProfiles(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	ids := make([]string, 0, len(a.profiles))
	for id := range a.profiles {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	list := make([]*Profile, 0, len(ids))
	for _, id := range ids {
		list = append(list, a.profiles[id])
	}
	w.Header().Set("Content-Type", "application/json")
	enc := json.NewEncoder(w)
	_ = enc.Encode(map[string]any{
		"server_version": serverVersion,
		"profiles":       list,
		// 行为模型参数包及其标定证据（§3.3）随 profiles 一并下发，供客户端盖入结果溯源、
		// 供评审核验「截至日期 X 本模拟是否匹配真实 AI」。additive 键，旧客户端忽略。
		"behavior_models": behaviorModelList(),
	})
}
