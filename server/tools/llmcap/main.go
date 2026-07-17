// llmcap：§3.3 标定采集器——对 **OpenAI 兼容** LLM 端点（kimi/deepseek/qwen 同协议）
// 发一次流式 chat 请求，逐 SSE chunk 记录 token 到达时刻与 wire 字节，输出 trace
// JSONL（behaviorspec.Trace 格式，一 run 一文件）供 tools/calibrate 拟合。
//
// 与 tools/capture 的分工：capture 抓 aneb-server 自有 /stream 格式（路径签名实验）；
// llmcap 抓**真实 LLM 端点** ground truth（E-03 标定证据链）。
//
// 代理策略（D-16 同款）：默认 Proxy:nil 强制直连；-proxy 显式给定才走代理。
// 密钥经 -key 或 LLM_API_KEY 环境变量传入，绝不写入 trace/meta/日志。
//
// 用法示例：
//
//	llmcap -url https://api.moonshot.cn/v1/chat/completions -model kimi-k2 \
//	       -prompt "介绍一下你自己" -max-tokens 600 -o kimi_run1.jsonl
//	（多次运行产出 run1..runN，交给 calibrate 聚合拟合）
package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"os"
	"time"

	"aneb-server/internal/behaviorspec"
)

const toolID = "llmcap/0.1"

func main() {
	endpoint := flag.String("url", "", "OpenAI-compatible chat completions URL (required)")
	model := flag.String("model", "", "model name (required)")
	prompt := flag.String("prompt", "请用中文写一段 500 字左右的短文，介绍大语言模型的工作原理。", "user prompt")
	maxTokens := flag.Int("max-tokens", 600, "max_tokens cap (cost guard)")
	key := flag.String("key", "", "API key (or env LLM_API_KEY); never written to output")
	outPath := flag.String("o", "", "output trace JSONL file (required)")
	proxy := flag.String("proxy", "", "explicit HTTP proxy URL (empty = direct, system proxy DISABLED)")
	timeout := flag.Duration("timeout", 180*time.Second, "overall request timeout")
	flag.Parse()
	if *endpoint == "" || *model == "" || *outPath == "" {
		flag.Usage()
		os.Exit(2)
	}
	apiKey := *key
	if apiKey == "" {
		apiKey = os.Getenv("LLM_API_KEY")
	}
	if apiKey == "" {
		log.Fatal("no API key: pass -key or set LLM_API_KEY")
	}

	body, err := json.Marshal(map[string]any{
		"model":      *model,
		"stream":     true,
		"max_tokens": *maxTokens,
		"messages":   []map[string]string{{"role": "user", "content": *prompt}},
	})
	if err != nil {
		log.Fatalf("marshal request: %v", err)
	}

	tr := &http.Transport{Proxy: nil}
	if *proxy != "" {
		pu, err := url.Parse(*proxy)
		if err != nil {
			log.Fatalf("bad -proxy: %v", err)
		}
		tr.Proxy = http.ProxyURL(pu)
	}
	client := &http.Client{Transport: tr, Timeout: *timeout}

	req, err := http.NewRequest(http.MethodPost, *endpoint, bytes.NewReader(body))
	if err != nil {
		log.Fatalf("build request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "text/event-stream")
	req.Header.Set("Authorization", "Bearer "+apiKey)

	anchor := time.Now() // 单调锚点：请求发出前（TTFT 口径起点，含连接建立——局限见 fitNote）
	resp, err := client.Do(req)
	if err != nil {
		log.Fatalf("request: %v", err)
	}
	defer resp.Body.Close()
	respHdrUs := time.Since(anchor).Microseconds()
	if resp.StatusCode != http.StatusOK {
		log.Fatalf("unexpected status: %s", resp.Status)
	}

	events, finish, skipped, err := behaviorspec.ParseOpenAIStream(resp.Body,
		func() int64 { return time.Since(anchor).Microseconds() })
	if err != nil {
		log.Fatalf("read stream: %v", err)
	}
	if skipped > 0 {
		log.Printf("WARNING: %d malformed data lines skipped", skipped)
	}

	t := behaviorspec.Trace{
		Meta: behaviorspec.TraceMeta{
			Endpoint:   *endpoint,
			Model:      *model,
			CapturedAt: anchor.UTC().Format(time.RFC3339),
			RespHdrUs:  respHdrUs,
			Tool:       toolID,
			PromptDesc: fmt.Sprintf("user prompt %dB, max_tokens=%d", len(*prompt), *maxTokens),
		},
		Events: events,
	}
	f, err := os.Create(*outPath)
	if err != nil {
		log.Fatalf("create output: %v", err)
	}
	defer f.Close()
	if err := behaviorspec.WriteTrace(f, t); err != nil {
		log.Fatalf("write trace: %v", err)
	}
	fmt.Printf("captured %d token events -> %s (finish=%q resp_header=%.1fms)\n",
		len(events), *outPath, finish, float64(respHdrUs)/1000)
}
