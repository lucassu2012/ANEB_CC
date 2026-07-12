// aneb-server：ANEB Probe 的 Agent 流量仿真服务器（阶段 0）。
// 仅标准库，无第三方依赖。设计依据：《ANEB Probe 开发设计文档》§4/§6
// 与《测量红队清单》R-04/R-06/R-07/R-08/R-17/R-20/R-23/R-24。
package main

import (
	"flag"
	"log"
	"net/http"
	"sync"
	"time"
)

const serverVersion = "aneb-server/0.1.0"

// app 汇集全部 handler 依赖（profile 表、数据目录）。
type app struct {
	profiles  map[string]*Profile
	dataDir   string
	resultsMu sync.Mutex
}

// routes 构建完整 handler 树（含 X-Aneb-Server 版本头中间件）。
func (a *app) routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/api/v1/echo", a.handleEcho)
	mux.HandleFunc("/api/v1/profiles", a.handleProfiles)
	mux.HandleFunc("/api/v1/stream", a.handleStream)
	mux.HandleFunc("/api/v1/upload", a.handleUpload)
	mux.HandleFunc("/api/v1/toolloop", a.handleToolLoop)
	mux.HandleFunc("/api/v1/results", a.handleResults)
	return withServerHeader(mux)
}

// withServerHeader 为所有响应附加 X-Aneb-Server 版本头——服务端指纹，
// 供客户端做路径劫持检测（响应不带指纹即判路径劫持而非计入失败率）。
func withServerHeader(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Aneb-Server", serverVersion)
		next.ServeHTTP(w, r)
	})
}

func main() {
	addr := flag.String("addr", ":8443", "listen address")
	// 默认路径用正斜杠：Go 在 Windows 同样接受，目标部署环境（Linux VM）
	// 反斜杠不是路径分隔符，`..\profiles` 会被当成字面文件名导致启动失败。
	profilesDir := flag.String("profiles", "../profiles", "profiles directory (versioned scenario JSON)")
	dataDir := flag.String("data", "./data", "data directory (results JSONL)")
	tlsCert := flag.String("tls-cert", "", "TLS certificate file (optional)")
	tlsKey := flag.String("tls-key", "", "TLS key file (optional)")
	flag.Parse()

	profiles, err := loadProfiles(*profilesDir)
	if err != nil {
		log.Fatalf("load profiles: %v", err)
	}
	for id, p := range profiles {
		log.Printf("profile loaded: %s v%s (%d phases)", id, p.Version, len(p.Phases))
	}

	a := &app{profiles: profiles, dataDir: *dataDir}

	// 超时策略：
	//   - ReadHeaderTimeout 防 slowloris（只限制读请求头，不影响 SSE 响应体流式写出）；
	//   - IdleTimeout 回收 keep-alive 空闲连接，防连接堆积；
	//   - 刻意不设 WriteTimeout：流式端点（S2 流 ~90s）会被整连接写超时截断，
	//     交给客户端 readTimeout 兜底；/stream pacing 循环内另有 r.Context()
	//     断开检测，客户端断开即退出。
	srv := &http.Server{
		Addr:              *addr,
		Handler:           a.routes(),
		ReadHeaderTimeout: 10 * time.Second,
		IdleTimeout:       120 * time.Second,
	}

	log.Printf("%s listening on %s (profiles=%s data=%s, mono-anchor wall=%d)",
		serverVersion, *addr, *profilesDir, *dataDir, anchorWallUnixNs)

	if *tlsCert != "" && *tlsKey != "" {
		log.Fatal(srv.ListenAndServeTLS(*tlsCert, *tlsKey))
	} else {
		log.Printf("WARNING: no -tls-cert/-tls-key given, serving PLAINTEXT HTTP — dev only, do not use for evidential runs")
		log.Fatal(srv.ListenAndServe())
	}
}
