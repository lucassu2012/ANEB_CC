// calibrate：§3.3 标定拟合器——把 tools/llmcap 采集的 trace JSONL（≥1 个 run）
// 拟合为**已标定**行为模型参数包 JSON（behaviorspec.Model，schema 与服务器
// -behavior-models 加载端同源），provenance 自动携带来源清单与拟合摘要。
//
// 拟合口径（详见 behaviorspec.Calibrate KDoc）：TTFT=各 run 首 token P50；
// rate_schedule=进度分段中位 TPS（仅非平稳时输出）；size_histogram=wire 字节频次；
// tokens_per_frame=到达聚簇众数。
//
// 用法示例：
//
//	calibrate -id kimi-k2 -provider kimi -pack-version v1 -o kimi-k2.json kimi_run*.jsonl
//	aneb-server -behavior-models ./models/   # 加载产物；profile phase 引用 behavior_model_id
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"os"

	"aneb-server/internal/behaviorspec"
)

func main() {
	id := flag.String("id", "", "pack id, e.g. kimi-k2 (required; no '@')")
	provider := flag.String("provider", "", "provider label, e.g. kimi/deepseek/qwen")
	version := flag.String("pack-version", "v1", "pack version (id@version stamps results)")
	outPath := flag.String("o", "", "output pack JSON file (required)")
	segments := flag.Int("segments", 0, "rate_schedule progress segments (0 = default 10)")
	coalesceUs := flag.Int64("coalesce-us", 0, "same-frame arrival threshold µs (0 = default 2000)")
	flag.Parse()
	files := flag.Args()
	if *id == "" || *outPath == "" || len(files) == 0 {
		fmt.Fprintln(os.Stderr, "usage: calibrate -id ID [-provider P] [-pack-version V] -o out.json trace1.jsonl [trace2.jsonl ...]")
		os.Exit(2)
	}

	traces, err := behaviorspec.ReadTraceFiles(files)
	if err != nil {
		log.Fatalf("read traces: %v", err)
	}
	m, report, err := behaviorspec.Calibrate(traces, behaviorspec.FitOptions{
		ID: *id, Version: *version, Provider: *provider,
		Segments: *segments, CoalesceUs: *coalesceUs,
	})
	if err != nil {
		log.Fatalf("calibrate: %v", err)
	}
	m.Provenance.Source = behaviorspec.SourceSummary(traces, files)

	data, err := json.MarshalIndent(m, "", "  ")
	if err != nil {
		log.Fatalf("marshal pack: %v", err)
	}
	if err := os.WriteFile(*outPath, append(data, '\n'), 0o644); err != nil {
		log.Fatalf("write pack: %v", err)
	}
	fmt.Printf("pack %s -> %s\n  %s\n", m.Stamp(), *outPath, report.Summary())
}
