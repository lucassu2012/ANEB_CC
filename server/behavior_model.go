package main

import (
	"fmt"
	"sort"
)

// BehaviorModel 是 AI 行为模拟的**版本化命名参数包**（设计 §3.3）。它是模型级
// §3.2 时序/字节旋钮的**单一事实源**：profile 的 token_stream phase 只需引用
// `behavior_model_id`，而非在每个 profile JSON 里重复同一组数字（INV-3，防漂移）。
//
// ## 分层（INV-2）
// pack 只给**模型固有默认**（TTFT 驻留形状、字节直方图、frame-batching、解码变速曲线）——
// 这些跨同一 provider 的各场景恒定；phase 给**场景参数**（token 数、基础速率）并可
// **覆盖**任意 pack 默认。解析口径="phase 已声明者胜、其余由 pack 补齐"（见
// streamParamsFromRequest 中 behavior-model 解析段）。省略 id ⇒ 无 pack ⇒ 行为不变。
//
// ## 标定证据（§3.3 最薄弱环）
// 每个 pack 随带 [Provenance]，把「这些数字从哪来」**显式化**——设计明言这是当前
// 框架最该补的证据链。未拟合真实端点的 pack 一律 `Calibrated=false` 且备注说明，
// 框架**绝不**为未标定 pack 声称「像真实 AI」（红线 §3.4：真实性声明由行为模型独占，
// 且须有 provenance 支撑）。
type BehaviorModel struct {
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

// Provenance 记录一个 pack 的数字来源——即 §3.3 的证据链。对任何尚未拟合到真实端点
// 采样 trace 的 pack，`Calibrated=false` + 诚实 Note 才是正确状态；框架从不为未标定 pack
// 声称真实性（红线 §3.4）。
type Provenance struct {
	Calibrated bool   `json:"calibrated"`
	Source     string `json:"source,omitempty"`      // trace 出处（capture id / 采样日期）
	FitSummary string `json:"fit_summary,omitempty"` // 残差 / 拟合优度
	Note       string `json:"note"`
}

// genericBehaviorModelID 是内置**未标定**通用包 id。它镜像历史全局 token 字节常数
// （median=120/sigma=0.6、无注入），存在的意义是把「未标定」这一事实**结构化并盖版本章**，
// 而非散落为裸常数。真实的逐 provider 包（kimi/deepseek/qwen）待 tools/capture 产出
// 拟合参数 + provenance 后新增（§3.3，外部依赖 E-03）。
const genericBehaviorModelID = "generic-uncalibrated"

// behaviorModels 是内置 pack 注册表——单一事实源。当前仅一个显式未标定的通用默认包。
// 派生自 defaultStreamMedian/Sigma（handlers_stream.go 常数），保证与请求级默认同源、不重复定义。
var behaviorModels = map[string]*BehaviorModel{
	genericBehaviorModelID: {
		ID:       genericBehaviorModelID,
		Version:  "v0",
		Provider: "",
		Median:   defaultStreamMedian,
		Sigma:    defaultStreamSigma,
		Provenance: Provenance{
			Calibrated: false,
			Note: "未标定通用默认——未拟合任何真实 provider；仅镜像历史全局 token 字节常数" +
				"(median/sigma)。切勿解读为匹配真实 kimi/deepseek/qwen。",
		},
	},
}

// lookupBehaviorModel 按 id 查 pack。空 id 返回 (nil,nil)（未引用 pack，行为不变）；
// 未知 id 返回错误（profile 引用了不存在的 pack 是坏契约，不做静默兜底）。
func lookupBehaviorModel(id string) (*BehaviorModel, error) {
	if id == "" {
		return nil, nil
	}
	m, ok := behaviorModels[id]
	if !ok {
		return nil, fmt.Errorf("unknown behavior_model_id: %s", id)
	}
	return m, nil
}

// stamp 返回 "id@version" 溯源印，供 wire prelude 透出、盖入结果溯源（与
// server_version/kpi_set/aqs_version 并列）。
func (m *BehaviorModel) stamp() string {
	if m == nil {
		return ""
	}
	return m.ID + "@" + m.Version
}

// applyDefaults 把 pack 的模型固有默认填入 params——**仅对 phase 未声明的旋钮**
// （phase 已声明者恒胜，INV-3 分层）。tokenBytesSet 表示 phase 是否显式声明了
// token_bytes（决定字节模型归谁）。确定性：pack 为静态常量，不触 rng。
func (m *BehaviorModel) applyDefaults(params *StreamParams, tokenBytesSet bool) {
	if m == nil {
		return
	}
	if params.TtftInjectUs == 0 {
		params.TtftInjectUs = m.TtftInjectUs
	}
	if params.TokensPerFrame == 0 {
		params.TokensPerFrame = m.TokensPerFrame
	}
	if len(params.RateSchedule) == 0 {
		params.RateSchedule = m.RateSchedule
	}
	// 字节模型：phase 声明了 token_bytes 就归 phase；否则由 pack 决定（直方图优先，其次 lognormal）。
	if !tokenBytesSet {
		if len(m.SizeHistogram) > 0 {
			params.SizeHistogram = m.SizeHistogram
		}
		if m.Median > 0 {
			params.Median = m.Median
		}
		if m.Sigma > 0 {
			params.Sigma = m.Sigma
		}
	}
	params.BehaviorModelStamp = m.stamp()
}

// behaviorModelList 返回按 id 升序排列的 pack 列表（供 /profiles 透出，确定性顺序）。
func behaviorModelList() []*BehaviorModel {
	ids := make([]string, 0, len(behaviorModels))
	for id := range behaviorModels {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	list := make([]*BehaviorModel, 0, len(ids))
	for _, id := range ids {
		list = append(list, behaviorModels[id])
	}
	return list
}
