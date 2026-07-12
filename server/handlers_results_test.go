package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"
)

func TestResultsAppendJsonl(t *testing.T) {
	dataDir := t.TempDir()
	a := &app{profiles: map[string]*Profile{}, dataDir: dataDir}
	srv := httptest.NewServer(a.routes())
	defer srv.Close()

	post := func(body string) *http.Response {
		resp, err := http.Post(srv.URL+"/api/v1/results", "application/json", strings.NewReader(body))
		if err != nil {
			t.Fatal(err)
		}
		t.Cleanup(func() { resp.Body.Close() })
		return resp
	}

	if resp := post(`{"run_id":"r1","aqs":88}`); resp.StatusCode != http.StatusOK {
		t.Fatalf("first post status %d", resp.StatusCode)
	}
	if resp := post("{\n  \"run_id\": \"r2\"\n}"); resp.StatusCode != http.StatusOK {
		t.Fatalf("second post status %d", resp.StatusCode)
	}

	path := filepath.Join(dataDir, "results", time.Now().Format("20060102")+".jsonl")
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read jsonl: %v", err)
	}
	lines := strings.Split(strings.TrimRight(string(data), "\n"), "\n")
	if len(lines) != 2 {
		t.Fatalf("got %d lines, want 2: %q", len(lines), string(data))
	}
	// 每行一个 compact JSON（多行输入被压成单行）。
	if lines[0] != `{"run_id":"r1","aqs":88}` {
		t.Fatalf("line 0 = %q", lines[0])
	}
	if strings.Contains(lines[1], "\n") || !strings.Contains(lines[1], `"run_id":"r2"`) {
		t.Fatalf("line 1 = %q", lines[1])
	}
}

func TestResultsRejectsInvalid(t *testing.T) {
	a := &app{profiles: map[string]*Profile{}, dataDir: t.TempDir()}
	srv := httptest.NewServer(a.routes())
	defer srv.Close()

	// 非 JSON。
	resp, err := http.Post(srv.URL+"/api/v1/results", "application/json", strings.NewReader("not json"))
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("invalid JSON: status %d, want 400", resp.StatusCode)
	}

	// 超过 1MB。
	big := bytes.Repeat([]byte("a"), (1<<20)+100)
	resp, err = http.Post(srv.URL+"/api/v1/results", "application/json", bytes.NewReader(big))
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusRequestEntityTooLarge {
		t.Fatalf("oversized: status %d, want 413", resp.StatusCode)
	}
}

// resultsMu 并发正确性：10 goroutine 同时 POST 不同 JSON，落盘必须恰好
// 10 行、每行可独立 json.Unmarshal（无交织/截断）、run_id 各出现一次。
func TestResultsConcurrent(t *testing.T) {
	dataDir := t.TempDir()
	a := &app{profiles: map[string]*Profile{}, dataDir: dataDir}
	srv := httptest.NewServer(a.routes())
	defer srv.Close()

	const workers = 10
	// pad 拉长行体，提升写交织（若锁失效）被撞出来的概率。
	pad := strings.Repeat("x", 512)
	errs := make([]error, workers)
	var wg sync.WaitGroup
	for i := 0; i < workers; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			body := fmt.Sprintf(`{"run_id":"concurrent-%d","idx":%d,"pad":%q}`, i, i, pad)
			resp, err := http.Post(srv.URL+"/api/v1/results", "application/json", strings.NewReader(body))
			if err != nil {
				errs[i] = err
				return
			}
			resp.Body.Close()
			if resp.StatusCode != http.StatusOK {
				errs[i] = fmt.Errorf("status %d", resp.StatusCode)
			}
		}(i)
	}
	wg.Wait()
	for i, err := range errs {
		if err != nil {
			t.Fatalf("worker %d: %v", i, err)
		}
	}

	path := filepath.Join(dataDir, "results", time.Now().Format("20060102")+".jsonl")
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read jsonl: %v", err)
	}
	lines := strings.Split(strings.TrimRight(string(data), "\n"), "\n")
	if len(lines) != workers {
		t.Fatalf("got %d lines, want %d", len(lines), workers)
	}
	seen := make(map[string]bool, workers)
	for i, ln := range lines {
		var obj struct {
			RunID string `json:"run_id"`
			Idx   int    `json:"idx"`
			Pad   string `json:"pad"`
		}
		if err := json.Unmarshal([]byte(ln), &obj); err != nil {
			t.Fatalf("line %d not independently parseable JSON: %v (%q)", i, err, ln)
		}
		if obj.RunID == "" || seen[obj.RunID] {
			t.Fatalf("line %d run_id %q missing or duplicated", i, obj.RunID)
		}
		if obj.Pad != pad {
			t.Fatalf("line %d pad corrupted (interleaved write?)", i)
		}
		seen[obj.RunID] = true
	}
}
