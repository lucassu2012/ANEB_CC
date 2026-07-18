package behaviorspec

import (
	"fmt"
	"math"
	"sort"
	"strings"
)

// 拟合/加载共用的旋钮边界（与服务器 /stream 参数校验同界，单一事实源）。
const (
	MaxTtftInjectUs   int64 = 10_000_000 // TTFT 注入上限 10s（防单请求 goroutine 长挂）
	MaxTokensPerFrame       = 64         // frame-batching 上限（防单帧过大）
	MinTps                  = 0.1        // rate_schedule tps 下限（同 validateRateSchedule）
	MaxTps                  = 100_000.0  // rate_schedule tps 上限（同上）
)

// 拟合默认参数。
const (
	defaultSegments   = 10   // rate_schedule 进度分段数
	defaultCoalesceUs = 2000 // 同帧聚簇阈值（µs）：到达间隔≤此值视为同一 SSE 帧
	defaultMaxBins    = 32   // 字节直方图最大桶数（超出等宽合并）
	scheduleRatio     = 1.15 // 段速 max/min ≥ 此比值才输出非平稳曲线（否则视为常速）
)

// FitOptions 是标定拟合的输入参数。ID/Version 必填；其余零值取默认。
type FitOptions struct {
	ID       string
	Version  string
	Provider string

	Segments   int   // rate_schedule 分段数（默认 10）
	CoalesceUs int64 // 同帧聚簇阈值 µs（默认 2000）
	MaxBins    int   // 直方图最大桶数（默认 32）
}

// FitReport 是拟合过程的统计报告——进 Provenance.FitSummary，供评审核验拟合优度。
type FitReport struct {
	Runs   int
	Tokens int

	TtftP10Us, TtftP50Us, TtftP90Us int64
	TtftClamped                     bool // p50 超 MaxTtftInjectUs 被 clamp（注入值≠原始 p50）

	MeanTps float64 // 各 run 全程 TPS 的均值
	TpsCv   float64 // 各 run 全程 TPS 的变异系数（std/mean）

	SegTpsMin, SegTpsMax float64 // 分段中位速的极值（非平稳性证据）
	ScheduleUsed         bool    // 是否输出了 rate_schedule（max/min≥1.15）
	ScheduleUnmeasured   bool    // 曲线**不可测**（run 过短 k<2 / 段内时刻并列）——区别于「近常速」

	TokensPerFrame int  // 聚簇众数（1=未见合帧）
	TpfAbandoned   bool // 众数超帧上限（>MaxTokensPerFrame）→ 判为快速流/采集粘连，未出 tokens_per_frame
	ClampedBytes   int  // wire 字节被 clamp 到 [TokenBytesMin,TokenBytesMax] 的事件数
	ClampedSegTps  int  // 段速越 [MinTps,MaxTps] 被 clamp 的段数（帧粘连/无节奏数据的诚实注记）
}

// Summary 输出人读拟合摘要（写入 Provenance.FitSummary）。
func (r *FitReport) Summary() string {
	var b strings.Builder
	fmt.Fprintf(&b, "runs=%d tokens=%d; TTFT p50=%.1fms (p10=%.1f p90=%.1f)",
		r.Runs, r.Tokens, float64(r.TtftP50Us)/1000, float64(r.TtftP10Us)/1000, float64(r.TtftP90Us)/1000)
	if r.TtftClamped {
		b.WriteString(" [注入值已 clamp 至 10s 上限]")
	}
	fmt.Fprintf(&b, "; TPS mean=%.2f cv=%.3f", r.MeanTps, r.TpsCv)
	switch {
	case r.ScheduleUsed:
		fmt.Fprintf(&b, "; 非平稳段速 [%.2f,%.2f] → rate_schedule", r.SegTpsMin, r.SegTpsMax)
	case r.ScheduleUnmeasured:
		b.WriteString("; 段速不可测（run 过短或到达时刻并列），未出 rate_schedule")
	default:
		fmt.Fprintf(&b, "; 段速 [%.2f,%.2f] 近常速（<%.0f%% 变幅），未出 rate_schedule",
			r.SegTpsMin, r.SegTpsMax, (scheduleRatio-1)*100)
	}
	switch {
	case r.TpfAbandoned:
		fmt.Fprintf(&b, "; 到达聚簇众数 %d 超帧上限 %d（快速流/采集粘连），未出 tokens_per_frame",
			r.TokensPerFrame, MaxTokensPerFrame)
	case r.TokensPerFrame > 1:
		fmt.Fprintf(&b, "; tokens_per_frame=%d（到达聚簇众数）", r.TokensPerFrame)
	}
	if r.ClampedBytes > 0 {
		fmt.Fprintf(&b, "; %d/%d 事件 wire 字节越界被 clamp", r.ClampedBytes, r.Tokens)
	}
	if r.ClampedSegTps > 0 {
		fmt.Fprintf(&b, "; %d 段速越界被 clamp（帧粘连/无节奏数据）", r.ClampedSegTps)
	}
	return b.String()
}

// fitNote 是所有标定包统一携带的口径局限声明（诚实边界，红线 §3.4）。
const fitNote = "标定包由 tools/llmcap 采集 + tools/calibrate 拟合。口径局限：" +
	"TTFT 含采集路径网络时延与连接建立（未剥离）；字节=SSE data 行线上字节" +
	"（含 JSON 信封，非 vendor token 计费口径）；tokens_per_frame/rate_schedule " +
	"为到达时刻经验估计（受采集路径网络抖动影响）。重放语义见 PROFILE_FRAMEWORK §3.2/§3.3。"

// SourceSummary 汇总各 trace 的采集来源（端点/模型/时刻去重列举 + 文件清单），
// 写入 Provenance.Source——评审据此追溯 ground truth。
func SourceSummary(traces []Trace, files []string) string {
	seen := map[string]bool{}
	var parts []string
	for _, t := range traces {
		key := t.Meta.Endpoint + " model=" + t.Meta.Model
		if !seen[key] {
			seen[key] = true
			parts = append(parts, key)
		}
	}
	s := strings.Join(parts, "; ")
	if len(traces) > 0 {
		s += fmt.Sprintf("; runs=%d captured=%s..%s", len(traces),
			traces[0].Meta.CapturedAt, traces[len(traces)-1].Meta.CapturedAt)
	}
	if len(files) > 0 {
		s += "; files=" + strings.Join(files, ",")
	}
	return s
}

// Calibrate 从采集 trace 拟合出**已标定**行为模型参数包（Calibrated=true + 完整
// provenance）。要求每 run ≥2 个 token 事件（残缺 run 直接报错——证据链不掺水）。
//
// 拟合口径：
//   - TtftInjectUs = 各 run 首 token 到达时刻的 P50（最近秩），clamp ≤10s；
//   - rate_schedule = 流内进度 K 等分的分段中位 TPS，仅当 max/min ≥ 1.15（非平稳
//     证据充分）才输出，否则省略（常速由 phase rate_tps 描述）；
//   - size_histogram = wire 字节频次（clamp [30,2000]；distinct 桶超上限时等宽合并）；
//   - tokens_per_frame = 到达间隔 ≤ CoalesceUs 的聚簇大小众数（=1 则省略）。
func Calibrate(traces []Trace, opts FitOptions) (*Model, *FitReport, error) {
	if opts.ID == "" || opts.Version == "" {
		return nil, nil, fmt.Errorf("calibrate: ID and Version are required")
	}
	if strings.Contains(opts.ID, "@") || strings.Contains(opts.Version, "@") {
		return nil, nil, fmt.Errorf("calibrate: ID/Version must not contain '@' (reserved for id@version stamp)")
	}
	if len(traces) == 0 {
		return nil, nil, fmt.Errorf("calibrate: no traces")
	}
	if opts.Segments <= 0 {
		opts.Segments = defaultSegments
	}
	if opts.CoalesceUs <= 0 {
		opts.CoalesceUs = defaultCoalesceUs
	}
	if opts.MaxBins <= 0 {
		opts.MaxBins = defaultMaxBins
	}
	for i, t := range traces {
		if len(t.Events) < 2 {
			return nil, nil, fmt.Errorf("calibrate: run %d has %d token events (<2) — capture incomplete", i, len(t.Events))
		}
		// 全部拟合数学（TTFT=首事件、span=末−首、插值、聚簇间隔）都假设到达时刻单调非负。
		// 乱序/负 trace（手编/拼接/损坏）若不拦，会静默出 Calibrated=true 的垃圾包——时序残缺
		// 与形状残缺同样是掺水，一并 fail-fast。
		if t.Events[0].ArrivalUs < 0 {
			return nil, nil, fmt.Errorf("calibrate: run %d event 0 has negative arrival_us %d", i, t.Events[0].ArrivalUs)
		}
		for j := 1; j < len(t.Events); j++ {
			if t.Events[j].ArrivalUs < t.Events[j-1].ArrivalUs {
				return nil, nil, fmt.Errorf("calibrate: run %d arrival_us not monotonic at event %d (%d < %d) — corrupt/out-of-order trace",
					i, j, t.Events[j].ArrivalUs, t.Events[j-1].ArrivalUs)
			}
		}
	}

	report := &FitReport{Runs: len(traces)}
	for _, t := range traces {
		report.Tokens += len(t.Events)
	}

	// —— TTFT：各 run 首 token 到达（最近秩分位）。
	ttfts := make([]int64, 0, len(traces))
	for _, t := range traces {
		ttfts = append(ttfts, t.Events[0].ArrivalUs)
	}
	sort.Slice(ttfts, func(i, j int) bool { return ttfts[i] < ttfts[j] })
	report.TtftP10Us = percentileNearestRank(ttfts, 0.10)
	report.TtftP50Us = percentileNearestRank(ttfts, 0.50)
	report.TtftP90Us = percentileNearestRank(ttfts, 0.90)
	ttftInject := report.TtftP50Us
	if ttftInject < 0 {
		ttftInject = 0
	}
	if ttftInject > MaxTtftInjectUs {
		ttftInject = MaxTtftInjectUs
		report.TtftClamped = true
	}

	// —— 全程 TPS 均值/变异系数（各 run 首→末 token 时距）。
	var tpsAll []float64
	for _, t := range traces {
		n := len(t.Events)
		span := t.Events[n-1].ArrivalUs - t.Events[0].ArrivalUs
		if span > 0 {
			tpsAll = append(tpsAll, float64(n-1)/(float64(span)/1e6))
		}
	}
	report.MeanTps, report.TpsCv = meanCv(tpsAll)

	// —— rate_schedule：进度 K 等分，段速跨 run 取中位。
	schedule, segMin, segMax, segClamped := fitRateSchedule(traces, opts.Segments)
	report.SegTpsMin, report.SegTpsMax = segMin, segMax
	report.ClampedSegTps = segClamped
	switch {
	case schedule == nil:
		// 曲线不可测（run 过短 k<2 或段内时刻并列）——区别于「近常速」，诚实注记（红线 §3.4）。
		report.ScheduleUnmeasured = true
	case segMin > 0 && segMax/segMin >= scheduleRatio:
		report.ScheduleUsed = true
	default:
		schedule = nil // 测得但近常速：常速由 phase rate_tps 描述
	}

	// —— 字节直方图（wire 字节，clamp + 等宽合并）。
	hist, clamped := fitHistogram(traces, opts.MaxBins)
	report.ClampedBytes = clamped

	// —— tokens_per_frame：聚簇众数。
	// 众数 > 帧上限 = 「整段流粘成一簇」——真实成因几乎总是**快速均匀流**或采集路径缓冲，
	// 而非 vendor 真在做 >64-token 巨帧批量。此时**放弃** tokens_per_frame（而非 clamp 到 64，
	// 那会把均匀快流误标成巨帧突发、重放 wire 与 ground truth 截然相反——审查确认缺陷）。
	report.TokensPerFrame = fitTokensPerFrame(traces, opts.CoalesceUs)
	tpf := 0
	switch {
	case report.TokensPerFrame > MaxTokensPerFrame:
		report.TpfAbandoned = true // 判为快速流/粘连，不写旋钮
	case report.TokensPerFrame > 1:
		tpf = report.TokensPerFrame
	}

	m := &Model{
		ID:             opts.ID,
		Version:        opts.Version,
		Provider:       opts.Provider,
		TtftInjectUs:   ttftInject,
		TokensPerFrame: tpf,
		RateSchedule:   schedule,
		SizeHistogram:  hist,
		Provenance: Provenance{
			Calibrated: true,
			FitSummary: report.Summary(),
			Note:       fitNote,
		},
	}
	return m, report, nil
}

// percentileNearestRank 最近秩分位（rank=ceil(p×n)，与 KpiCalculator 同口径）。
// 调用方保证 sorted 非空且已升序。
func percentileNearestRank(sorted []int64, p float64) int64 {
	rank := int(math.Ceil(p * float64(len(sorted))))
	if rank < 1 {
		rank = 1
	}
	if rank > len(sorted) {
		rank = len(sorted)
	}
	return sorted[rank-1]
}

// meanCv 返回均值与变异系数（总体标准差/均值）。空输入返回 0,0。
func meanCv(xs []float64) (mean, cv float64) {
	if len(xs) == 0 {
		return 0, 0
	}
	for _, x := range xs {
		mean += x
	}
	mean /= float64(len(xs))
	if mean == 0 {
		return 0, 0
	}
	var ss float64
	for _, x := range xs {
		d := x - mean
		ss += d * d
	}
	return mean, math.Sqrt(ss/float64(len(xs))) / mean
}

// arrivalAtFrac 在到达序列上按分数 token 位置线性插值到达时刻。
// frac∈[0,1] 映射 token 位置 x=frac×(n-1)。
func arrivalAtFrac(events []TraceEvent, frac float64) float64 {
	n := len(events)
	x := frac * float64(n-1)
	i := int(math.Floor(x))
	if i >= n-1 {
		return float64(events[n-1].ArrivalUs)
	}
	f := x - float64(i)
	return float64(events[i].ArrivalUs) + f*float64(events[i+1].ArrivalUs-events[i].ArrivalUs)
}

// fitRateSchedule 把每 run 的流按进度 K 等分求段 TPS，跨 run 取段中位，输出
// K 个断点（AtFrac=段中点）。返回曲线、段速极值（判非平稳用）与越界 clamp 段数。
// 段数会被压到 ≤ (最短 run 的间隔数)/2——段内至少 2 个间隔才有测速意义。
// 段速 clamp 到 [MinTps,MaxTps]（服务器 validateRateSchedule 同界）——保证 calibrate
// 产物**免编辑即可被服务器加载**；clamp 属帧粘连/无节奏数据的诚实注记（进 report）。
func fitRateSchedule(traces []Trace, segments int) (sched []RatePoint, segMin, segMax float64, clamped int) {
	minIntervals := math.MaxInt
	for _, t := range traces {
		if n := len(t.Events) - 1; n < minIntervals {
			minIntervals = n
		}
	}
	k := segments
	if k > minIntervals/2 {
		k = minIntervals / 2
	}
	if k < 2 {
		return nil, 0, 0, 0
	}

	segTps := make([][]float64, k)
	for _, t := range traces {
		n := len(t.Events)
		tokensPerSeg := float64(n-1) / float64(k)
		for j := 0; j < k; j++ {
			f0, f1 := float64(j)/float64(k), float64(j+1)/float64(k)
			t0, t1 := arrivalAtFrac(t.Events, f0), arrivalAtFrac(t.Events, f1)
			if t1 > t0 {
				segTps[j] = append(segTps[j], tokensPerSeg/((t1-t0)/1e6))
			}
		}
	}

	sched = make([]RatePoint, 0, k)
	for j := 0; j < k; j++ {
		if len(segTps[j]) == 0 {
			return nil, 0, 0, 0 // 有段无有效样本（时刻并列）→ 放弃曲线，回常速
		}
		med := medianFloat(segTps[j])
		if med < MinTps {
			med = MinTps
			clamped++
		} else if med > MaxTps {
			med = MaxTps
			clamped++
		}
		mid := (float64(j) + 0.5) / float64(k)
		sched = append(sched, RatePoint{AtFrac: round3(mid), Tps: round3(med)})
		if segMin == 0 || med < segMin {
			segMin = med
		}
		if med > segMax {
			segMax = med
		}
	}
	return sched, segMin, segMax, clamped
}

// fitHistogram 统计 wire 字节频次（clamp [TokenBytesMin,TokenBytesMax]），
// distinct 尺寸超 maxBins 时等宽合并（桶代表值=桶内加权均值）。按 Size 升序输出。
func fitHistogram(traces []Trace, maxBins int) (bins []SizeBin, clamped int) {
	counts := map[int]float64{}
	for _, t := range traces {
		for _, e := range t.Events {
			s := e.WireBytes
			if s < TokenBytesMin {
				s = TokenBytesMin
				clamped++
			} else if s > TokenBytesMax {
				s = TokenBytesMax
				clamped++
			}
			counts[s]++
		}
	}
	sizes := make([]int, 0, len(counts))
	for s := range counts {
		sizes = append(sizes, s)
	}
	sort.Ints(sizes)

	if len(sizes) <= maxBins {
		for _, s := range sizes {
			bins = append(bins, SizeBin{Size: s, Weight: counts[s]})
		}
		return bins, clamped
	}

	// 等宽合并：[min,max] 均分 maxBins 桶；代表值=桶内加权均值（必在桶内，无碰撞）。
	lo, hi := sizes[0], sizes[len(sizes)-1]
	width := int(math.Ceil(float64(hi-lo+1) / float64(maxBins)))
	type acc struct{ wSum, sSum float64 }
	accs := make([]acc, maxBins)
	for _, s := range sizes {
		idx := (s - lo) / width
		if idx >= maxBins {
			idx = maxBins - 1
		}
		accs[idx].wSum += counts[s]
		accs[idx].sSum += counts[s] * float64(s)
	}
	for _, a := range accs {
		if a.wSum > 0 {
			bins = append(bins, SizeBin{Size: int(math.Round(a.sSum / a.wSum)), Weight: a.wSum})
		}
	}
	return bins, clamped
}

// fitTokensPerFrame 把每 run 内到达间隔 ≤ coalesceUs 的相邻事件聚为一簇，
// 返回簇大小众数（并列取小）。1 = 未观察到合帧。
func fitTokensPerFrame(traces []Trace, coalesceUs int64) int {
	freq := map[int]int{}
	for _, t := range traces {
		cluster := 1
		for i := 1; i < len(t.Events); i++ {
			if t.Events[i].ArrivalUs-t.Events[i-1].ArrivalUs <= coalesceUs {
				cluster++
			} else {
				freq[cluster]++
				cluster = 1
			}
		}
		freq[cluster]++
	}
	mode, modeN := 1, 0
	for size, n := range freq {
		if n > modeN || (n == modeN && size < mode) {
			mode, modeN = size, n
		}
	}
	return mode
}

func medianFloat(xs []float64) float64 {
	s := append([]float64(nil), xs...)
	sort.Float64s(s)
	n := len(s)
	if n%2 == 1 {
		return s[n/2]
	}
	return (s[n/2-1] + s[n/2]) / 2
}

func round3(x float64) float64 { return math.Round(x*1000) / 1000 }
