package behaviorspec

import (
	"bufio"
	"encoding/json"
	"io"
	"strings"
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
	br := bufio.NewReaderSize(r, 64*1024)
	for {
		line, readErr := br.ReadString('\n')
		arrival := now()
		line = strings.TrimRight(line, "\r\n")
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
		if readErr != nil {
			if readErr == io.EOF {
				return events, finishReason, skipped, nil
			}
			return events, finishReason, skipped, readErr
		}
	}
}
