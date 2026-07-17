package behaviorspec

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"strings"
)

// 面向**不受信网络端点**的防护上限（被劫持/故障的「OpenAI 兼容」端点可能狂灌）：
const (
	maxSSELineBytes = 4 << 20 // 单 SSE 行 4MB 上限（防不发换行的无界缓冲）
	maxStreamEvents = 200_000 // 单流 token 事件硬顶（防无限 data 行 OOM）
)

// oaChunk 是 OpenAI 兼容 chat.completion.chunk 中本层关心的字段。
type oaChunk struct {
	Choices []struct {
		Delta struct {
			Role    string `json:"role"`
			Content string `json:"content"`
		} `json:"delta"`
		FinishReason *string `json:"finish_reason"`
	} `json:"choices"`
}

// ParseOpenAIStream 逐行解析 OpenAI 兼容 SSE 流（kimi/deepseek/qwen 同协议），
// 产出 token 事件序列：每个**非空 content delta** 记一个事件；role 帧（content 空）
// 与纯 finish 帧不计为 token（与 APP 侧 ApiProbe 适配器口径一致）。
//
//   - now：到达时刻源（返回相对请求锚点的 µs）——注入以便单测给确定值；采集器传
//     单调时钟差。事件 arrival 取「读到该 data 行」的时刻。
//   - 返回 finishReason（空=流未见 finish）与 skipped（畸形 data 行数——跳过不
//     静默错位，计数供采集器上报）。
//   - `data: [DONE]` 或 EOF 正常收尾。
func ParseOpenAIStream(r io.Reader, now func() int64) (events []TraceEvent, finishReason string, skipped int, err error) {
	sc := bufio.NewScanner(r)
	sc.Buffer(make([]byte, 0, 64*1024), maxSSELineBytes)
	for {
		if !sc.Scan() {
			if serr := sc.Err(); serr != nil {
				if serr == bufio.ErrTooLong {
					return events, finishReason, skipped, fmt.Errorf("SSE line exceeds %d bytes (untrusted endpoint?)", maxSSELineBytes)
				}
				return events, finishReason, skipped, serr
			}
			return events, finishReason, skipped, nil // EOF：正常收尾（部分 vendor 无 [DONE]）
		}
		arrival := now()
		line := strings.TrimRight(sc.Text(), "\r")
		if data, ok := strings.CutPrefix(line, "data: "); ok {
			if data == "[DONE]" {
				return events, finishReason, skipped, nil
			}
			var c oaChunk
			if jsonErr := json.Unmarshal([]byte(data), &c); jsonErr != nil {
				skipped++
			} else if len(c.Choices) > 0 {
				ch := c.Choices[0]
				if ch.Delta.Content != "" {
					if len(events) >= maxStreamEvents {
						return events, finishReason, skipped, fmt.Errorf("stream exceeds %d token events (untrusted endpoint?)", maxStreamEvents)
					}
					events = append(events, TraceEvent{
						Index:        len(events),
						ArrivalUs:    arrival,
						WireBytes:    len(data),
						ContentBytes: len(ch.Delta.Content),
					})
				}
				if ch.FinishReason != nil && *ch.FinishReason != "" {
					finishReason = *ch.FinishReason
				}
			}
		}
	}
}
