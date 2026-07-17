package behaviorspec

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"os"
)

// TraceMeta 是一次采集 run 的元数据（llmcap 写入 trace 首行，进 provenance.Source）。
type TraceMeta struct {
	Endpoint   string `json:"endpoint"`              // 采集端点 URL（不含任何密钥）
	Model      string `json:"model"`                 // 请求的模型名
	CapturedAt string `json:"captured_at"`           // RFC3339 采集时刻
	RespHdrUs  int64  `json:"resp_header_us"`        // 请求发出→响应头到达（连接+首包，供 TTFT 口径核对）
	Tool       string `json:"tool,omitempty"`        // 采集器标识（如 "llmcap/0.1"）
	PromptDesc string `json:"prompt_desc,omitempty"` // prompt 摘要（长度/类别，不含原文）
}

// TraceEvent 是一个 token 事件（一个非空 content delta）。
type TraceEvent struct {
	Index     int   `json:"index"`      // 0 起 token 序号
	ArrivalUs int64 `json:"arrival_us"` // 相对请求发出锚点的单调到达时刻（µs）
	// WireBytes 是该 SSE `data:` 行 payload 的线上字节数（含 JSON 信封）。
	// 字节直方图拟合用它——服务器 token payload 模拟的是「每 token 下行字节」，
	// 纯 content 字节会系统性低估（信封开销真实占带宽）。
	WireBytes    int `json:"wire_bytes"`
	ContentBytes int `json:"content_bytes"` // delta.content 的 UTF-8 字节数（伴随统计）
}

// Trace 是一次采集 run 的完整记录。
type Trace struct {
	Meta   TraceMeta
	Events []TraceEvent
}

// traceLine 是 trace JSONL 的一行联合体（type 区分 meta/token）。
type traceLine struct {
	Type string `json:"type"`
	*TraceMeta
	*TraceEvent
}

// WriteTrace 以 JSONL 写出：首行 meta、其后逐事件一行。
func WriteTrace(w io.Writer, t Trace) error {
	enc := json.NewEncoder(w)
	if err := enc.Encode(traceLine{Type: "meta", TraceMeta: &t.Meta}); err != nil {
		return err
	}
	for i := range t.Events {
		if err := enc.Encode(traceLine{Type: "token", TraceEvent: &t.Events[i]}); err != nil {
			return err
		}
	}
	return nil
}

// ReadTrace 解析一份 trace JSONL。首行必须是 meta；token 行按出现顺序收集。
func ReadTrace(r io.Reader) (Trace, error) {
	var t Trace
	sc := bufio.NewScanner(r)
	sc.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	lineNo := 0
	for sc.Scan() {
		lineNo++
		raw := sc.Bytes()
		if len(raw) == 0 {
			continue
		}
		var line traceLine
		if err := json.Unmarshal(raw, &line); err != nil {
			return t, fmt.Errorf("trace line %d: %w", lineNo, err)
		}
		switch line.Type {
		case "meta":
			if line.TraceMeta == nil {
				return t, fmt.Errorf("trace line %d: meta line without fields", lineNo)
			}
			t.Meta = *line.TraceMeta
		case "token":
			if line.TraceEvent == nil {
				return t, fmt.Errorf("trace line %d: token line without fields", lineNo)
			}
			t.Events = append(t.Events, *line.TraceEvent)
		default:
			return t, fmt.Errorf("trace line %d: unknown type %q", lineNo, line.Type)
		}
	}
	if err := sc.Err(); err != nil {
		return t, err
	}
	if t.Meta.CapturedAt == "" && len(t.Events) == 0 {
		return t, fmt.Errorf("empty trace")
	}
	return t, nil
}

// ReadTraceFiles 读取多个 trace 文件（一 run 一文件），任一失败即整体报错——
// 标定输入是证据链，不允许静默跳过残缺 run。
func ReadTraceFiles(paths []string) ([]Trace, error) {
	traces := make([]Trace, 0, len(paths))
	for _, p := range paths {
		f, err := os.Open(p)
		if err != nil {
			return nil, fmt.Errorf("open %s: %w", p, err)
		}
		t, err := ReadTrace(f)
		f.Close()
		if err != nil {
			return nil, fmt.Errorf("parse %s: %w", p, err)
		}
		traces = append(traces, t)
	}
	return traces, nil
}
