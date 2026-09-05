# verify_trial_f2 · DW-20260905-02（DeepSeek 四格批，大脑自开窗）

- 条件：wifi；功能：F2；提示词：`Think step by step and explain in detail: why is the square root of 2 irrational?`；轮数 1；答窗 120s ＋ 静置 20s（实际值见包级 `verify_trial_f2_driver_timing.jsonl` 逐轮）
- **开关态（D-641）**：深度思考ON+智能搜索OFF（am kill 冷启后搜索复位为 ON，本格启动后手动点 (545,2525) 关闭并像素核对）；模式选择器=快速模式(默认未动)（截图自读确认，图未存档）
- 驱动器：`tools/e234/drive_cell_ds.py`@`99d07b2`；采集器参数：`--session-seconds 300 --screencap-period-ms 1500 --framestats-period-s 1 --no-marks`；ROI 400,1800,400,200
- 设备：P40 Pro `8MY0221126002537`；DeepSeek versionName=2.2.2（lastUpdateTime=2026-07-19 15:02:06）；探针 `com.aneb.probe.ctree`（lastUpdateTime=2026-09-04 09:02:32；P1a 恰一进程）
- 制式：pre=`NR_SA,Unknown` post=`NR_SA,Unknown`；路由 pre=`1.1.1.1 via 10.10.0.1 dev wlan0 table 1040 src 10.10.7.37 uid 2000 ` post=`1.1.1.1 via 10.10.0.1 dev wlan0 table 1040 src 10.10.7.37 uid 2000 `
- 刷新周期首行：`16666666`；退出码：driver=0 collector=0 precheck=1；步 1a/1c/4b 与逐轮 a/c 簇与帧数见 `orchestrator.log`
- 口径：自然对照版（无整形）；P1 判读按命题单 §2（轮内 C 侧间隔计数），`e2_precheck` 判词作参考信号
