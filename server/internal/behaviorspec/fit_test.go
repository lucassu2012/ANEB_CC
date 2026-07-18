package behaviorspec

import (
	"bytes"
	"math"
	"strings"
	"testing"
)

// mkTrace 构造 n 个事件的 trace：arrival 由 at(i) 给出，wire 字节由 wb(i) 给出。
func mkTrace(n int, at func(i int) int64, wb func(i int) int) Trace {
	t := Trace{Meta: TraceMeta{Endpoint: "http://e", Model: "m", CapturedAt: "2026-07-17T00:00:00Z"}}
	for i := 0; i < n; i++ {
		t.Events = append(t.Events, TraceEvent{Index: i, ArrivalUs: at(i), WireBytes: wb(i), ContentBytes: 3})
	}
	return t
}

func constWb(b int) func(int) int { return func(int) int { return b } }

// ---- 分位（最近秩，与 KpiCalculator 同口径） ----

func TestPercentileNearestRank(t *testing.T) {
	s := []int64{10, 20, 30}
	if percentileNearestRank(s, 0.10) != 10 || percentileNearestRank(s, 0.50) != 20 || percentileNearestRank(s, 0.90) != 30 {
		t.Fatal("nearest-rank percentiles wrong")
	}
	// 偶数 n 的 p50 取低位（rank=ceil(0.5×2)=1）
	if percentileNearestRank([]int64{100, 200}, 0.50) != 100 {
		t.Fatal("even-n p50 must take lower rank")
	}
}

// ---- 聚簇 tokens_per_frame ----

func TestFitTokensPerFrameClusters(t *testing.T) {
	// 3 簇全为 3 token（簇内间隔 100µs ≤ 2000，簇间 10ms）→ 众数 3
	tr := mkTrace(9, func(i int) int64 {
		return int64(i/3)*10_000 + int64(i%3)*100
	}, constWb(100))
	if got := fitTokensPerFrame([]Trace{tr}, 2000); got != 3 {
		t.Fatalf("tokens_per_frame = %d, want 3", got)
	}
	// 均匀 25ms 间隔 → 全部单簇 → 1
	tr2 := mkTrace(10, func(i int) int64 { return int64(i) * 25_000 }, constWb(100))
	if got := fitTokensPerFrame([]Trace{tr2}, 2000); got != 1 {
		t.Fatalf("uniform stream tokens_per_frame = %d, want 1", got)
	}
}

// ---- 字节直方图 ----

func TestFitHistogramClampAndOrder(t *testing.T) {
	sizes := []int{100, 100, 100, 200, 200, 10} // 10 越下界 → clamp 30
	tr := mkTrace(len(sizes), func(i int) int64 { return int64(i) * 25_000 }, func(i int) int { return sizes[i] })
	bins, clamped := fitHistogram([]Trace{tr}, 32)
	if clamped != 1 {
		t.Fatalf("clamped = %d, want 1", clamped)
	}
	want := []SizeBin{{Size: 30, Weight: 1}, {Size: 100, Weight: 3}, {Size: 200, Weight: 2}}
	if len(bins) != len(want) {
		t.Fatalf("bins = %+v", bins)
	}
	for i := range want {
		if bins[i] != want[i] {
			t.Fatalf("bin %d = %+v, want %+v", i, bins[i], want[i])
		}
	}
}

func TestFitHistogramMergesWideDistribution(t *testing.T) {
	// 100 个 distinct 尺寸（40..139）→ 合并至 ≤32 桶且权重和守恒
	tr := mkTrace(100, func(i int) int64 { return int64(i) * 25_000 }, func(i int) int { return 40 + i })
	bins, _ := fitHistogram([]Trace{tr}, 32)
	if len(bins) == 0 || len(bins) > 32 {
		t.Fatalf("merged bins = %d, want (0,32]", len(bins))
	}
	var w float64
	for _, b := range bins {
		w += b.Weight
		if b.Size < TokenBytesMin || b.Size > TokenBytesMax {
			t.Fatalf("merged bin size %d out of clamp range", b.Size)
		}
	}
	if w != 100 {
		t.Fatalf("total weight = %v, want 100", w)
	}
}

// ---- 非平稳曲线 ----

// 前半 100tps（间隔 10ms）后半 50tps（间隔 20ms）→ 段速首≈100 末≈50、递减。
func TestFitRateScheduleDecayingStream(t *testing.T) {
	n := 101
	at := func(i int) int64 {
		if i <= 50 {
			return int64(i) * 10_000
		}
		return 500_000 + int64(i-50)*20_000
	}
	tr := mkTrace(n, at, constWb(100))
	sched, segMin, segMax, _ := fitRateSchedule([]Trace{tr}, 10)
	if len(sched) != 10 {
		t.Fatalf("schedule points = %d, want 10", len(sched))
	}
	if math.Abs(sched[0].Tps-100) > 3 || math.Abs(sched[9].Tps-50) > 3 {
		t.Fatalf("edge seg tps = %.2f / %.2f, want ≈100 / ≈50", sched[0].Tps, sched[9].Tps)
	}
	if segMax/segMin < scheduleRatio {
		t.Fatalf("max/min = %.3f should exceed ratio threshold", segMax/segMin)
	}
	// AtFrac 严格递增 ∈ (0,1)
	for i := 1; i < len(sched); i++ {
		if sched[i].AtFrac <= sched[i-1].AtFrac {
			t.Fatal("at_frac must be strictly increasing")
		}
	}
}

// 常速流 → Calibrate 不输出 rate_schedule（<15% 变幅）。
func TestCalibrateConstantRateOmitsSchedule(t *testing.T) {
	tr1 := mkTrace(60, func(i int) int64 { return 300_000 + int64(i)*25_000 }, constWb(120))
	tr2 := mkTrace(60, func(i int) int64 { return 500_000 + int64(i)*25_000 }, constWb(120))
	m, report, err := Calibrate([]Trace{tr1, tr2}, FitOptions{ID: "t", Version: "v1"})
	if err != nil {
		t.Fatal(err)
	}
	if m.RateSchedule != nil || report.ScheduleUsed {
		t.Fatalf("constant-rate stream must omit schedule: %+v", m.RateSchedule)
	}
	// TTFT：runs 首 token [300000,500000] → 偶数 n p50=低位 300000
	if m.TtftInjectUs != 300_000 {
		t.Fatalf("ttft = %d, want 300000", m.TtftInjectUs)
	}
	// 25ms 间隔无聚簇 → tokens_per_frame 省略
	if m.TokensPerFrame != 0 {
		t.Fatalf("tokens_per_frame = %d, want 0", m.TokensPerFrame)
	}
	// 40tps 全程速率
	if math.Abs(report.MeanTps-40) > 0.5 {
		t.Fatalf("mean tps = %.2f, want ≈40", report.MeanTps)
	}
	// 直方图恒 120B 单桶
	if len(m.SizeHistogram) != 1 || m.SizeHistogram[0].Size != 120 {
		t.Fatalf("histogram = %+v", m.SizeHistogram)
	}
	// provenance：Calibrated=true、Note/FitSummary 非空
	if !m.Provenance.Calibrated || m.Provenance.Note == "" || m.Provenance.FitSummary == "" {
		t.Fatalf("provenance incomplete: %+v", m.Provenance)
	}
	if m.Stamp() != "t@v1" {
		t.Fatalf("stamp = %q", m.Stamp())
	}
}

// 减速流 → Calibrate 输出 rate_schedule。
func TestCalibrateDecayingRateEmitsSchedule(t *testing.T) {
	at := func(i int) int64 {
		if i <= 50 {
			return 200_000 + int64(i)*10_000
		}
		return 700_000 + int64(i-50)*20_000
	}
	m, report, err := Calibrate([]Trace{mkTrace(101, at, constWb(120))}, FitOptions{ID: "t", Version: "v1"})
	if err != nil {
		t.Fatal(err)
	}
	if len(m.RateSchedule) == 0 || !report.ScheduleUsed {
		t.Fatal("decaying stream must emit rate_schedule")
	}
	if !strings.Contains(m.Provenance.FitSummary, "rate_schedule") {
		t.Fatalf("fit summary should mention schedule: %s", m.Provenance.FitSummary)
	}
}

// 输入校验：缺 ID / ID|Version 带 @ / 空 traces / 残缺 run / 乱序或负到达 一律报错。
func TestCalibrateInputValidation(t *testing.T) {
	ok := mkTrace(5, func(i int) int64 { return int64(i+1) * 25_000 }, constWb(100))
	desc := mkTrace(5, func(i int) int64 { return int64(5-i) * 25_000 }, constWb(100)) // 严格递减
	neg := mkTrace(3, func(i int) int64 { return int64(i-1) * 1000 }, constWb(100))    // 首事件 -1000
	cases := []struct {
		name   string
		traces []Trace
		opts   FitOptions
	}{
		{"missing id", []Trace{ok}, FitOptions{Version: "v1"}},
		{"id with @", []Trace{ok}, FitOptions{ID: "a@b", Version: "v1"}},
		{"version with @", []Trace{ok}, FitOptions{ID: "a", Version: "v1@rc"}},
		{"no traces", nil, FitOptions{ID: "t", Version: "v1"}},
		{"short run", []Trace{mkTrace(1, func(int) int64 { return 1000 }, constWb(100))}, FitOptions{ID: "t", Version: "v1"}},
		{"non-monotonic arrival", []Trace{desc}, FitOptions{ID: "t", Version: "v1"}},
		{"negative arrival", []Trace{neg}, FitOptions{ID: "t", Version: "v1"}},
	}
	for _, c := range cases {
		if _, _, err := Calibrate(c.traces, c.opts); err == nil {
			t.Fatalf("%s: expected error", c.name)
		}
	}
}

// tokens_per_frame 众数 > 帧上限（快速均匀流/采集粘连）→ **放弃**旋钮（不 clamp 到 64，
// 那会把均匀快流误标成巨帧突发），FitSummary 诚实注记。审查确认的 medium 缺陷回归护栏。
func TestCalibrateFastStreamAbandonsTokensPerFrame(t *testing.T) {
	// 100 token 间隔 1500µs（667tps，≤默认 coalesce 2000）→ 整段聚一簇、众数 100 > 64。
	tr := mkTrace(100, func(i int) int64 { return 300_000 + int64(i)*1500 }, constWb(120))
	m, report, err := Calibrate([]Trace{tr}, FitOptions{ID: "fast", Version: "v1"})
	if err != nil {
		t.Fatal(err)
	}
	if m.TokensPerFrame != 0 {
		t.Fatalf("fast uniform stream must NOT emit tokens_per_frame, got %d", m.TokensPerFrame)
	}
	if !report.TpfAbandoned {
		t.Fatal("report.TpfAbandoned must be set")
	}
	if !strings.Contains(m.Provenance.FitSummary, "超帧上限") {
		t.Fatalf("fit summary must note abandonment: %s", m.Provenance.FitSummary)
	}
}

// 真合帧（众数 ≤ 上限）仍如实输出 tokens_per_frame。
func TestCalibrateGenuineBatchingEmitsTokensPerFrame(t *testing.T) {
	// 每 4 token 一簇（簇内 100µs、簇间 25ms），共 40 token → 众数 4。
	tr := mkTrace(40, func(i int) int64 { return 200_000 + int64(i/4)*25_000 + int64(i%4)*100 }, constWb(120))
	m, _, err := Calibrate([]Trace{tr}, FitOptions{ID: "batch", Version: "v1"})
	if err != nil {
		t.Fatal(err)
	}
	if m.TokensPerFrame != 4 {
		t.Fatalf("genuine batching tokens_per_frame = %d, want 4", m.TokensPerFrame)
	}
}

// 曲线**不可测**（run 过短，k<2）与「近常速」在 FitSummary 中必须区分（红线 §3.4 诚实边界）。
func TestCalibrateScheduleUnmeasuredVsConstant(t *testing.T) {
	// 3 事件 run：间隔数 2 → k=min(10,2/2)=1 <2 → 曲线不可测。
	short := mkTrace(3, func(i int) int64 { return 100_000 + int64(i)*25_000 }, constWb(120))
	m, report, err := Calibrate([]Trace{short}, FitOptions{ID: "s", Version: "v1"})
	if err != nil {
		t.Fatal(err)
	}
	if !report.ScheduleUnmeasured || report.ScheduleUsed {
		t.Fatalf("short run must be ScheduleUnmeasured, got %+v", report)
	}
	if !strings.Contains(m.Provenance.FitSummary, "不可测") || strings.Contains(m.Provenance.FitSummary, "近常速") {
		t.Fatalf("unmeasured summary must say 不可测 not 近常速: %s", m.Provenance.FitSummary)
	}
	// 对照：长常速流 → 近常速措辞。
	long := mkTrace(60, func(i int) int64 { return 300_000 + int64(i)*25_000 }, constWb(120))
	m2, r2, _ := Calibrate([]Trace{long}, FitOptions{ID: "c", Version: "v1"})
	if r2.ScheduleUnmeasured || !strings.Contains(m2.Provenance.FitSummary, "近常速") {
		t.Fatalf("constant stream must say 近常速: %s", m2.Provenance.FitSummary)
	}
}

// 段速 clamp 分支（帧粘连微秒并列→段速爆表）确定性覆盖 + ClampedSegTps 断言。
func TestFitRateScheduleClampsExtremeSegTps(t *testing.T) {
	// 前半间隔 1µs（≈1e6 tps 越 MaxTps）、后半 20ms → 触发上界 clamp。
	at := func(i int) int64 {
		if i <= 50 {
			return int64(i) * 1
		}
		return 500_000 + int64(i-50)*20_000
	}
	sched, _, segMax, clamped := fitRateSchedule([]Trace{mkTrace(101, at, constWb(120))}, 10)
	if clamped == 0 {
		t.Fatal("expected at least one clamped segment")
	}
	if segMax > MaxTps {
		t.Fatalf("seg tps %.1f exceeds MaxTps after clamp", segMax)
	}
	for _, p := range sched {
		if p.Tps < MinTps || p.Tps > MaxTps {
			t.Fatalf("clamped schedule point %v out of [MinTps,MaxTps]", p)
		}
	}
}

// 跨 run 段中位聚合（calibrate 主用法 kimi_run*.jsonl）：两条速度不同的 run 中位应居中。
func TestFitRateScheduleAggregatesAcrossRuns(t *testing.T) {
	fast := mkTrace(101, func(i int) int64 { return int64(i) * 10_000 }, constWb(120)) // 100tps
	slow := mkTrace(101, func(i int) int64 { return int64(i) * 20_000 }, constWb(120)) // 50tps
	sched, segMin, segMax, _ := fitRateSchedule([]Trace{fast, slow}, 10)
	if len(sched) == 0 {
		t.Fatal("expected schedule")
	}
	// 两 run 各段常速 100/50，跨 run 中位=两者中位 75（偶数取低=... medianFloat 2 元取均值 75）
	for _, p := range sched {
		if p.Tps < 60 || p.Tps > 90 {
			t.Fatalf("cross-run median tps %.2f not centered ~75", p.Tps)
		}
	}
	_ = segMin
	_ = segMax
}

// ---- trace 往返 ----

func TestTraceWriteReadRoundtrip(t *testing.T) {
	orig := mkTrace(3, func(i int) int64 { return int64(i+1) * 1000 }, constWb(77))
	orig.Meta.Tool = "llmcap/0.1"
	var buf bytes.Buffer
	if err := WriteTrace(&buf, orig); err != nil {
		t.Fatal(err)
	}
	got, err := ReadTrace(&buf)
	if err != nil {
		t.Fatal(err)
	}
	if got.Meta != orig.Meta {
		t.Fatalf("meta roundtrip: %+v != %+v", got.Meta, orig.Meta)
	}
	if len(got.Events) != len(orig.Events) {
		t.Fatalf("events = %d", len(got.Events))
	}
	for i := range orig.Events {
		if got.Events[i] != orig.Events[i] {
			t.Fatalf("event %d roundtrip mismatch", i)
		}
	}
}

func TestReadTraceRejectsGarbage(t *testing.T) {
	if _, err := ReadTrace(strings.NewReader(`{"type":"wat"}` + "\n")); err == nil {
		t.Fatal("unknown type must error")
	}
	if _, err := ReadTrace(strings.NewReader("")); err == nil {
		t.Fatal("empty trace must error")
	}
}
