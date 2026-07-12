package main

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"time"
)

const resultsMaxBytes = 1 << 20 // 1MB

// handleResults POST /api/v1/results：接收结果上报，追加写
// <dataDir>/results/YYYYMMDD.jsonl，每行一个 JSON（compact）。
// 文件名日期用墙钟——这是日志归档命名，不是逐事件时间戳，不违反 R-24。
func (a *app) handleResults(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	body, err := io.ReadAll(http.MaxBytesReader(w, r.Body, resultsMaxBytes))
	if err != nil {
		http.Error(w, "body too large or unreadable", http.StatusRequestEntityTooLarge)
		return
	}
	if len(body) == 0 || !json.Valid(body) {
		http.Error(w, "body must be a single JSON document", http.StatusBadRequest)
		return
	}
	var line bytes.Buffer
	line.Grow(len(body) + 1)
	if err := json.Compact(&line, body); err != nil {
		http.Error(w, "invalid JSON", http.StatusBadRequest)
		return
	}
	line.WriteByte('\n')

	dir := filepath.Join(a.dataDir, "results")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		http.Error(w, "storage error", http.StatusInternalServerError)
		return
	}
	path := filepath.Join(dir, time.Now().Format("20060102")+".jsonl")

	a.resultsMu.Lock()
	defer a.resultsMu.Unlock()
	f, err := os.OpenFile(path, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
	if err != nil {
		http.Error(w, "storage error", http.StatusInternalServerError)
		return
	}
	defer f.Close()
	if _, err := f.Write(line.Bytes()); err != nil {
		http.Error(w, "storage error", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(`{"ok":true}`))
}
