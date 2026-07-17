package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"aneb-server/internal/behaviorspec"
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
//
// 类型定义下沉 behaviorspec（标定管线 tools/llmcap→tools/calibrate 产物与服务器
// 加载共用同一 JSON schema），此处别名保持主包 API 不变。
type BehaviorModel = behaviorspec.Model

// Provenance 记录一个 pack 的数字来源——即 §3.3 的证据链（别名，定义见 behaviorspec）。
type Provenance = behaviorspec.Provenance

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

// applyBehaviorModelDefaults 把 pack 的模型固有默认填入 params——**仅对 phase 未声明
// 的旋钮**（phase 已声明者恒胜，INV-3 分层）。tokenBytesSet 表示 phase 是否显式声明了
// token_bytes（决定字节模型归谁）。确定性：pack 为静态数据，不触 rng。
// （原为 *BehaviorModel 方法；类型别名化后 Go 禁止对非本包类型加方法，改普通函数——
// StreamParams 属主包，不宜下沉。）
func applyBehaviorModelDefaults(m *BehaviorModel, params *StreamParams, tokenBytesSet bool) {
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
	params.BehaviorModelStamp = m.Stamp()
}

// loadBehaviorModels 从目录读取 *.json 参数包（tools/calibrate 产物，schema=
// behaviorspec.Model 单一事实源），逐包校验后并入内置注册表。任一文件解析/校验
// 失败即整体报错（参数包是行为模拟合同，不允许静默跳过）；与内置或彼此重复 id
// 亦报错。dir 为空 = 仅内置（行为不变）。
func loadBehaviorModels(dir string) error {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return fmt.Errorf("read behavior-models dir %s: %w", dir, err)
	}
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(strings.ToLower(e.Name()), ".json") {
			continue
		}
		path := filepath.Join(dir, e.Name())
		data, err := os.ReadFile(path)
		if err != nil {
			return fmt.Errorf("read %s: %w", path, err)
		}
		var m BehaviorModel
		if err := json.Unmarshal(data, &m); err != nil {
			return fmt.Errorf("parse %s: %w", path, err)
		}
		if err := validateBehaviorModel(&m); err != nil {
			return fmt.Errorf("validate %s: %w", path, err)
		}
		if _, dup := behaviorModels[m.ID]; dup {
			return fmt.Errorf("duplicate behavior_model id %q in %s", m.ID, path)
		}
		behaviorModels[m.ID] = &m
	}
	return nil
}

// validateBehaviorModel 校验参数包字段——旋钮边界与 /stream 请求校验同界
// （behaviorspec 常量单源），provenance 的 Note 必填（证据链是本类型存在的意义）。
func validateBehaviorModel(m *BehaviorModel) error {
	if m.ID == "" || m.Version == "" {
		return fmt.Errorf("missing id or version")
	}
	if strings.Contains(m.ID, "@") {
		return fmt.Errorf("id must not contain '@' (reserved for id@version stamp)")
	}
	if m.TtftInjectUs < 0 || m.TtftInjectUs > behaviorspec.MaxTtftInjectUs {
		return fmt.Errorf("ttft_inject_us out of range [0,%d]", behaviorspec.MaxTtftInjectUs)
	}
	if m.TokensPerFrame < 0 || m.TokensPerFrame > behaviorspec.MaxTokensPerFrame {
		return fmt.Errorf("tokens_per_frame out of range [0,%d]", behaviorspec.MaxTokensPerFrame)
	}
	if err := validateRateSchedule(m.RateSchedule, false); err != nil {
		return err
	}
	if err := validateSizeHistogram(m.SizeHistogram); err != nil {
		return err
	}
	if m.Median < 0 || m.Sigma < 0 {
		return fmt.Errorf("median/sigma must be >= 0")
	}
	if strings.TrimSpace(m.Provenance.Note) == "" {
		return fmt.Errorf("provenance.note is required (evidence chain, red-line §3.4)")
	}
	return nil
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
