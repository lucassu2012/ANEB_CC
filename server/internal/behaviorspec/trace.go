package behaviorspec

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"net/url"
	"os"
	"strings"
)

// secretQueryKeys 是常见网关把凭据塞进 URL query 的键名（小写匹配）。
var secretQueryKeys = map[string]bool{
	"key": true, "api_key": true, "apikey": true,
	"access_token": true, "token": true, "auth": true,
}

// SanitizeEndpoint 去除 URL 中的凭据后返回可安全写入 trace/provenance/日志的字符串：
// 剥离 userinfo（user:pass@）与常见密钥 query 参数（值替换为 REDACTED）。
// 解析失败则截到 '?' 前（宁可少信息也不泄密钥）。绝不把原始 URL 落地——trace/包
// 会经 /profiles 公开透出。
func SanitizeEndpoint(raw string) string {
	u, err := url.Parse(raw)
	if err != nil {
		if i := strings.IndexByte(raw, '?'); i >= 0 {
			return raw[:i] + "?[unparseable-redacted]"
		}
		return raw
	}
	u.User = nil
	if q := u.Query(); len(q) > 0 {
		for k := range q {
			if secretQueryKeys[strings.ToLower(k)] {
				q.Set(k, "REDACTED")
			}
		}
		u.RawQuery = q.Encode()
	}
	return u.String()
}

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

// ReadTrace 解析一份 trace JSONL。**首行必须是 meta 且仅一条**；token 行按出现
// 顺序收集。强制 meta 是证据链纪律（标定输入不许掺水）：token-only / 无 meta /
// 多 meta（多 run 误 cat 进一个文件）一律报错，绝不静默出残缺来源的包。
func ReadTrace(r io.Reader) (Trace, error) {
	var t Trace
	sc := bufio.NewScanner(r)
	sc.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	lineNo, metaSeen := 0, false
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
			if metaSeen {
				return t, fmt.Errorf("trace line %d: duplicate meta (多 run 误合并入一文件？)", lineNo)
			}
			if len(t.Events) > 0 {
				return t, fmt.Errorf("trace line %d: meta must be first line (token lines precede it)", lineNo)
			}
			t.Meta = *line.TraceMeta
			metaSeen = true
		case "token":
			if line.TraceEvent == nil {
				return t, fmt.Errorf("trace line %d: token line without fields", lineNo)
			}
			if !metaSeen {
				return t, fmt.Errorf("trace line %d: token line before meta (first line must be meta)", lineNo)
			}
			t.Events = append(t.Events, *line.TraceEvent)
		default:
			return t, fmt.Errorf("trace line %d: unknown type %q", lineNo, line.Type)
		}
	}
	if err := sc.Err(); err != nil {
		return t, err
	}
	if !metaSeen {
		return t, fmt.Errorf("trace has no meta line")
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
