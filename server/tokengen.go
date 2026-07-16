package main

import (
	"math"
	"math/rand"
)

// token 大小 clamp 区间（字节）。
const (
	tokenBytesMin = 30
	tokenBytesMax = 2000
)

// TokenSpec 是时刻表中的一个 token：计划发出时刻（相对流起点的微秒偏移）与 payload 字节数。
type TokenSpec struct {
	SchedUs int64 // 相对流起点的计划发出偏移
	Size    int   // base64 编码前的原始 payload 字节数
}

// StreamParams 是 token 发生器的全部输入。同一组参数（尤其同 Seed）
// 必须产生完全相同的 TokenSpec 序列——profile 冻结 + seed 固定是横比前提。
type StreamParams struct {
	Seed    int64
	Tokens  int
	RateTps float64
	Median  float64 // token_bytes.median
	Sigma   float64 // token_bytes.sigma
	Burst   *Burst  // nil = 均匀 1/rate_tps

	// TtftInjectUs 是首 token 前注入的确定性 TTFT 驻留（模拟 AI 排队/prefill/think，
	// 设计 §3.2/§3.4）。整表统一右移该偏移：首 token 计划于 TtftInjectUs（而非 0），
	// token 间间隔不变——只把 dwell 记进"起点→首 token"，不污染 ITL。服务端经 prelude
	// 显式透出该值供 APP 从 T1 减去（补"减法项恒为 0"缺口）。默认 0 = 无注入、行为不变。
	TtftInjectUs int64

	// RateSchedule 是**非平稳解码 TPS 曲线**（设计 §3.2「上下文衰减 rate_schedule 非平稳」）：
	// 按流内进度分段线性给出瞬时 TPS，逐 token 累积间隔——模拟真实 LLM 随上下文增长的解码变速
	// （典型前快后慢）。nil/空 = 常速 RateTps（原逻辑，行为不变）。仅均匀模式生效（burst 自有节奏）。
	RateSchedule []RatePoint

	// TokensPerFrame 是 **SSE frame-batching**（§3.2）：每帧合并的 token 数——纯 wire 层框帧，
	// 不影响 token 时刻表（GenerateTokens 忽略本字段），由 handler 在发送时按此合并 flush。
	// 1/0 = 每 token 一帧（默认，行为不变）。
	TokensPerFrame int
}

// RatePoint 是非平稳解码 TPS 曲线上的一个断点：流内进度 AtFrac∈[0,1] 处的瞬时 TPS。
type RatePoint struct {
	AtFrac float64 `json:"at_frac"`
	Tps    float64 `json:"tps"`
}

// tpsAtSchedule 在**已按 AtFrac 升序**的曲线上分段线性求 frac 处 TPS；端点外 clamp。
// 空曲线返回 fallback。调用方保证 sched 非空且已排序、Tps>0（streamParamsFromRequest 校验）。
func tpsAtSchedule(sched []RatePoint, frac, fallback float64) float64 {
	if len(sched) == 0 {
		return fallback
	}
	if frac <= sched[0].AtFrac {
		return sched[0].Tps
	}
	last := sched[len(sched)-1]
	if frac >= last.AtFrac {
		return last.Tps
	}
	for i := 1; i < len(sched); i++ {
		a, b := sched[i-1], sched[i]
		if frac <= b.AtFrac {
			if b.AtFrac == a.AtFrac {
				return b.Tps
			}
			return a.Tps + (frac-a.AtFrac)/(b.AtFrac-a.AtFrac)*(b.Tps-a.Tps)
		}
	}
	return last.Tps // 不可达
}

// GenerateTokens 生成确定性的 token 时刻表与大小序列。
//
// 随机数消耗顺序（固定，保证确定性）：
//   - 均匀模式：每 token 依次 1 次 NormFloat64（大小）。
//   - burst 模式：每簇开始 1 次 Float64（簇长，几何分布），
//     簇内每 token 1 次 NormFloat64（大小），
//     簇结束且还有后续 token 时 1 次 Float64（簇间停顿）。
//
// 大小分布：lognormal，size = median * exp(sigma*N(0,1))，clamp [30, 2000]。
func GenerateTokens(p StreamParams) []TokenSpec {
	if p.Tokens <= 0 {
		return nil
	}
	rng := rand.New(rand.NewSource(p.Seed))
	specs := make([]TokenSpec, p.Tokens)

	drawSize := func() int {
		v := p.Median * math.Exp(p.Sigma*rng.NormFloat64())
		n := int(math.Round(v))
		if n < tokenBytesMin {
			n = tokenBytesMin
		}
		if n > tokenBytesMax {
			n = tokenBytesMax
		}
		return n
	}

	if p.Burst == nil {
		if len(p.RateSchedule) == 0 {
			// 常速路径（原逻辑）：间隔恒定 1/RateTps。
			intervalUs := 1e6 / p.RateTps
			for i := 0; i < p.Tokens; i++ {
				specs[i] = TokenSpec{
					// 整表右移 TtftInjectUs（首 token 前的注入 dwell，§3.4）；间隔不变。
					SchedUs: int64(math.Round(float64(i)*intervalUs)) + p.TtftInjectUs,
					Size:    drawSize(),
				}
			}
			return specs
		}
		// 非平稳路径（§3.2）：按进度 frac=i/(N-1) 取瞬时 TPS，逐 token 累积间隔。
		// drawSize() 仍每 token 一次、顺序不变——确定性与常速路径同源。
		denom := float64(p.Tokens - 1)
		if denom < 1 {
			denom = 1
		}
		schedUs := 0.0
		for i := 0; i < p.Tokens; i++ {
			specs[i] = TokenSpec{
				SchedUs: int64(math.Round(schedUs)) + p.TtftInjectUs,
				Size:    drawSize(),
			}
			tps := tpsAtSchedule(p.RateSchedule, float64(i)/denom, p.RateTps)
			schedUs += 1e6 / tps // 本 token 后的间隔由本 token 处的瞬时 TPS 决定
		}
		return specs
	}

	// burst 模式：簇内 cluster_tps，簇长几何分布（均值 1/p），簇间停顿均匀 [min,max] ms。
	intraUs := 1e6 / p.Burst.ClusterTps
	pauseMinMs, pauseMaxMs := 0.0, 0.0
	if len(p.Burst.PauseMs) >= 2 {
		pauseMinMs = float64(p.Burst.PauseMs[0])
		pauseMaxMs = float64(p.Burst.PauseMs[1])
	} else if len(p.Burst.PauseMs) == 1 {
		pauseMinMs = float64(p.Burst.PauseMs[0])
		pauseMaxMs = pauseMinMs
	}

	t := 0.0 // 当前 token 的计划偏移（us，浮点累计自簇锚点，见下）
	i := 0
	for i < p.Tokens {
		clusterLen := geometric(rng, p.Burst.ClusterGeomP)
		last := 0.0
		for j := 0; j < clusterLen && i < p.Tokens; j++ {
			sched := t + float64(j)*intraUs
			// 整表右移 TtftInjectUs（§3.4）；last/t 用未偏移的相对时刻累计，间隔不变。
			specs[i] = TokenSpec{SchedUs: int64(math.Round(sched)) + p.TtftInjectUs, Size: drawSize()}
			last = sched
			i++
		}
		if i < p.Tokens {
			pauseMs := pauseMinMs + rng.Float64()*(pauseMaxMs-pauseMinMs)
			t = last + pauseMs*1000.0
		}
	}
	return specs
}

// geometric 返回 >=1 的几何分布样本（成功概率 p，均值 1/p）。
// 用逆变换法：一次 Float64 消耗，保证随机数消耗量与样本值无关之外的确定性。
func geometric(rng *rand.Rand, p float64) int {
	if p <= 0 || p >= 1 {
		return 1
	}
	u := rng.Float64()
	// P(X >= k) = (1-p)^(k-1)；X = floor(ln(1-u)/ln(1-p)) + 1
	k := int(math.Floor(math.Log(1-u)/math.Log(1-p))) + 1
	if k < 1 {
		k = 1
	}
	return k
}
