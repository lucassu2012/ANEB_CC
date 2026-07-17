// Package behaviorspec 是 §3.3 行为模型参数包的**共享合同层**：类型（wire JSON）、
// 采集 trace 格式、OpenAI 兼容 SSE 解析与标定拟合，全部集中一处，供主服务端
// （类型别名引用）与 tools/llmcap、tools/calibrate（薄 CLI）共同消费——
// 采集↔拟合↔加载↔重放共用同一份定义，杜绝两处漂移（设计 INV-3）。
package behaviorspec

// Token payload 字节 clamp 区间（与 tokengen 的发生器口径同源——主包经别名引用）。
const (
	TokenBytesMin = 30
	TokenBytesMax = 2000
)

// RatePoint 是非平稳解码 TPS 曲线上的一个断点：流内进度 AtFrac∈[0,1] 处的瞬时 TPS。
type RatePoint struct {
	AtFrac float64 `json:"at_frac"`
	Tps    float64 `json:"tps"`
}

// SizeBin 是字节直方图的一个桶：字节数 Size 与相对权重 Weight（>0）。
type SizeBin struct {
	Size   int     `json:"size"`
	Weight float64 `json:"weight"`
}

// Model 是 AI 行为模拟的**版本化命名参数包**（设计 §3.3）。字段语义见主包
// behavior_model.go 的 KDoc（分层解析：phase 已声明者胜、其余由包补齐）。
// 本类型同时是包文件（tools/calibrate 产物、服务器 -behavior-models 目录加载）
// 的 JSON schema——单一事实源。
type Model struct {
	ID       string `json:"id"`
	Version  string `json:"version"`
	Provider string `json:"provider,omitempty"` // "" = 通用/未标定；真实包填 kimi/deepseek/qwen

	// §3.2 模型固有默认（phase 未声明该旋钮时由此补齐；phase 已声明者恒胜）。
	TtftInjectUs   int64       `json:"ttft_inject_us,omitempty"`
	TokensPerFrame int         `json:"tokens_per_frame,omitempty"`
	RateSchedule   []RatePoint `json:"rate_schedule,omitempty"`
	SizeHistogram  []SizeBin   `json:"size_histogram,omitempty"`
	Median         float64     `json:"median,omitempty"` // 直方图为空时的 lognormal 兜底
	Sigma          float64     `json:"sigma,omitempty"`

	Provenance Provenance `json:"provenance"`
}

// Stamp 返回 "id@version" 溯源印，供 wire prelude 透出、盖入结果溯源（与
// server_version/kpi_set/aqs_version 并列）。nil 安全（未引用包 ⇒ 空印）。
func (m *Model) Stamp() string {
	if m == nil {
		return ""
	}
	return m.ID + "@" + m.Version
}

// Provenance 记录一个包的数字来源——§3.3 的证据链。未拟合真实端点的包一律
// Calibrated=false + 诚实 Note；框架绝不为未标定包声称真实性（红线 §3.4）。
type Provenance struct {
	Calibrated bool   `json:"calibrated"`
	Source     string `json:"source,omitempty"`      // trace 出处（端点/模型/采集时间/文件清单）
	FitSummary string `json:"fit_summary,omitempty"` // 样本量 / 分布统计 / 拟合残差
	Note       string `json:"note"`
}
