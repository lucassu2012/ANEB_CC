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

// 输入校验：缺 ID / ID 带 @ / 空 traces / 残缺 run 一律报错。
func TestCalibrateInputValidation(t *testing.T) {
	ok := mkTrace(5, func(i int) int64 { return int64(i+1) * 25_000 }, constWb(100))
	cases := []struct {
		name   string
		traces []Trace
		opts   FitOptions
	}{
		{"missing id", []Trace{ok}, FitOptions{Version: "v1"}},
		{"id with @", []Trace{ok}, FitOptions{ID: "a@b", Version: "v1"}},
		{"no traces", nil, FitOptions{ID: "t", Version: "v1"}},
		{"short run", []Trace{mkTrace(1, func(int) int64 { return 1000 }, constWb(100))}, FitOptions{ID: "t", Version: "v1"}},
	}
	for _, c := range cases {
		if _, _, err := Calibrate(c.traces, c.opts); err == nil {
			t.Fatalf("%s: expected error", c.name)
		}
	}
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
