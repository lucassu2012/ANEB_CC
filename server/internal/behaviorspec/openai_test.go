package behaviorspec

import (
	"strings"
	"testing"
)

// seqNow 返回每调一次 +1000µs 的到达时刻源（测试确定性——解析器每读一行调一次）。
func seqNow() func() int64 {
	var t int64
	return func() int64 {
		t += 1000
		return t
	}
}

const oaStream = `data: {"choices":[{"delta":{"role":"assistant","content":""},"finish_reason":null}]}

data: {"choices":[{"delta":{"content":"你好"},"finish_reason":null}]}

data: {"choices":[{"delta":{"content":"，世界"},"finish_reason":null}]}

data: {"choices":[{"delta":{"content":"!"},"finish_reason":null}]}

data: {"choices":[{"delta":{},"finish_reason":"stop"}],"usage":{"total_tokens":15}}

data: [DONE]

`

// role 帧不计 token；3 个 content 帧各记一事件（arrival=对应 data 行的 now 值）；
// finish 捕获；[DONE] 收尾。wire 字节=data 行 payload 长度；content 字节=UTF-8 长度。
func TestParseOpenAIStreamBasic(t *testing.T) {
	events, finish, skipped, err := ParseOpenAIStream(strings.NewReader(oaStream), seqNow())
	if err != nil {
		t.Fatal(err)
	}
	if skipped != 0 {
		t.Fatalf("skipped = %d, want 0", skipped)
	}
	if finish != "stop" {
		t.Fatalf("finish = %q, want stop", finish)
	}
	if len(events) != 3 {
		t.Fatalf("events = %d, want 3", len(events))
	}
	// 行序：role(1000) 空(2000) c1(3000) 空(4000) c2(5000) 空(6000) c3(7000)…
	wantArrival := []int64{3000, 5000, 7000}
	wantContent := []int{6, 9, 1} // "你好"=6B、"，世界"=9B、"!"=1B
	for i, e := range events {
		if e.Index != i {
			t.Fatalf("event %d index = %d", i, e.Index)
		}
		if e.ArrivalUs != wantArrival[i] {
			t.Fatalf("event %d arrival = %d, want %d", i, e.ArrivalUs, wantArrival[i])
		}
		if e.ContentBytes != wantContent[i] {
			t.Fatalf("event %d content bytes = %d, want %d", i, e.ContentBytes, wantContent[i])
		}
		if e.WireBytes <= e.ContentBytes {
			t.Fatalf("event %d wire bytes %d must exceed content bytes %d (JSON envelope)", i, e.WireBytes, e.ContentBytes)
		}
	}
}

// 畸形 data 行跳过并计数，不错位后续事件。
func TestParseOpenAIStreamMalformed(t *testing.T) {
	s := "data: {not json}\n\n" +
		`data: {"choices":[{"delta":{"content":"ok"},"finish_reason":null}]}` + "\n\ndata: [DONE]\n\n"
	events, _, skipped, err := ParseOpenAIStream(strings.NewReader(s), seqNow())
	if err != nil {
		t.Fatal(err)
	}
	if skipped != 1 || len(events) != 1 || events[0].ContentBytes != 2 {
		t.Fatalf("skipped=%d events=%+v", skipped, events)
	}
}

// 无 [DONE] 直接 EOF：正常收尾（部分 vendor 直接断流）。
func TestParseOpenAIStreamEOFWithoutDone(t *testing.T) {
	s := `data: {"choices":[{"delta":{"content":"a"},"finish_reason":null}]}` + "\n\n"
	events, finish, _, err := ParseOpenAIStream(strings.NewReader(s), seqNow())
	if err != nil {
		t.Fatal(err)
	}
	if len(events) != 1 || finish != "" {
		t.Fatalf("events=%d finish=%q", len(events), finish)
	}
}
