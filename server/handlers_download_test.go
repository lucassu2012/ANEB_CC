package main

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strconv"
	"testing"
)

// GET ?bytes=N：状态 200、Content-Length=N、实际读到 N 字节、X-Aneb-Download-Bytes=N、
// octet-stream 且 identity（不压缩，wire 字节=Content-Length）。
func TestDownloadExactBytesAndHeaders(t *testing.T) {
	a := &app{profiles: map[string]*Profile{}, dataDir: t.TempDir()}
	srv := httptest.NewServer(a.routes())
	defer srv.Close()

	const n = 1 << 20 // 1MiB
	resp, err := http.Get(srv.URL + "/api/v1/download?bytes=" + strconv.Itoa(n))
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("status %d", resp.StatusCode)
	}
	if got := resp.Header.Get("Content-Length"); got != strconv.Itoa(n) {
		t.Fatalf("Content-Length = %q, want %d", got, n)
	}
	if got := resp.Header.Get("X-Aneb-Download-Bytes"); got != strconv.Itoa(n) {
		t.Fatalf("X-Aneb-Download-Bytes = %q, want %d", got, n)
	}
	if ct := resp.Header.Get("Content-Type"); ct != "application/octet-stream" {
		t.Fatalf("Content-Type = %q", ct)
	}
	read, err := io.Copy(io.Discard, resp.Body)
	if err != nil {
		t.Fatalf("read body: %v", err)
	}
	if read != n {
		t.Fatalf("read %d bytes, want %d", read, n)
	}
}

// bytes 超过 1GiB 上限 → 400；0/负数亦然。
func TestDownloadRejectsOutOfRangeBytes(t *testing.T) {
	a := &app{profiles: map[string]*Profile{}, dataDir: t.TempDir()}
	srv := httptest.NewServer(a.routes())
	defer srv.Close()

	for _, q := range []string{"bytes=0", "bytes=-1", "bytes=1073741825"} { // 末者 = 1GiB+1
		resp, err := http.Get(srv.URL + "/api/v1/download?" + q)
		if err != nil {
			t.Fatal(err)
		}
		resp.Body.Close()
		if resp.StatusCode != http.StatusBadRequest {
			t.Fatalf("%s: status %d, want 400", q, resp.StatusCode)
		}
	}
}

// 非 GET → 405。
func TestDownloadRejectsNonGet(t *testing.T) {
	a := &app{profiles: map[string]*Profile{}, dataDir: t.TempDir()}
	srv := httptest.NewServer(a.routes())
	defer srv.Close()

	resp, err := http.Post(srv.URL+"/api/v1/download", "application/octet-stream", nil)
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusMethodNotAllowed {
		t.Fatalf("status %d, want 405", resp.StatusCode)
	}
}
