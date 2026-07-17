package behaviorspec

import (
	"strings"
	"testing"
)

// meta 强制：token-only / meta-after-token / 双 meta 一律报错（证据链不掺水）。
func TestReadTraceEnforcesMeta(t *testing.T) {
	tokenLine := `{"type":"token","index":0,"arrival_us":1000,"wire_bytes":80}`
	metaLine := `{"type":"meta","endpoint":"http://e","model":"m","captured_at":"2026-07-17T00:00:00Z"}`
	bad := map[string]string{
		"token only":       tokenLine + "\n",
		"meta after token": tokenLine + "\n" + metaLine + "\n",
		"double meta":      metaLine + "\n" + metaLine + "\n",
		"no meta empty":    "",
	}
	for name, s := range bad {
		if _, err := ReadTrace(strings.NewReader(s)); err == nil {
			t.Fatalf("%s: expected error", name)
		}
	}
	// 合法：meta 首行 + token
	if _, err := ReadTrace(strings.NewReader(metaLine + "\n" + tokenLine + "\n")); err != nil {
		t.Fatalf("valid trace rejected: %v", err)
	}
	// 合法：meta 无 token（0 事件）——ReadTrace 接受，Calibrate 才拒 <2
	if tr, err := ReadTrace(strings.NewReader(metaLine + "\n")); err != nil || len(tr.Events) != 0 {
		t.Fatalf("meta-only should parse with 0 events: err=%v", err)
	}
}

// SanitizeEndpoint 剥 userinfo 与密钥 query，保留路径。
func TestSanitizeEndpoint(t *testing.T) {
	cases := []struct{ in, mustHave, mustNotHave string }{
		{"https://api.x.com/v1/chat/completions?key=AIzaSECRET", "REDACTED", "AIzaSECRET"},
		{"https://user:p4ss@host/v1/completions", "host/v1/completions", "p4ss"},
		{"https://api.x.com/v1/chat?api_key=sk-xyz&model=k2", "REDACTED", "sk-xyz"},
		{"https://api.x.com/v1/chat/completions", "api.x.com/v1/chat/completions", "REDACTED"},
	}
	for _, c := range cases {
		got := SanitizeEndpoint(c.in)
		if !strings.Contains(got, c.mustHave) {
			t.Fatalf("sanitize(%q)=%q missing %q", c.in, got, c.mustHave)
		}
		if c.mustNotHave != "REDACTED" && strings.Contains(got, c.mustNotHave) {
			t.Fatalf("sanitize(%q)=%q leaked secret %q", c.in, got, c.mustNotHave)
		}
	}
}
