# cell_f6 · DW-20260905-01（P2 两腿先行批，大脑自开窗）

- 条件：cell；功能：F6 图像生成；提示词：`Generate an image of a red circle on a white background.`；轮数 6；答窗 75s ＋ 静置 20s（实际值见包级 `cell_f6_driver_timing.jsonl` 逐轮）
- 驱动器：`tools/e234/drive_cell.py`@`99d07b2`（A-1 四件后）；采集器参数：`--session-seconds 700 --screencap-period-ms 1500 --framestats-period-s 1 --no-marks`；ROI 400,1800,400,200
- 设备：P40 Pro `8MY0221126002537`；豆包 versionName=14.9.0；探针包 `com.aneb.probe.ctree`（P1a 恰一进程）
- 制式：pre=`NR_SA,Unknown` post=`NR_SA,Unknown`；路由 pre=`1.1.1.1 via 10.121.106.242 dev rmnet0 table 1008 src 10.121.106.242 uid 2000 ` post=`1.1.1.1 via 10.121.106.242 dev rmnet0 table 1008 src 10.121.106.242 uid 2000 `
- 退出码：driver=0 collector=0；步 1a/1c/4b 输出见 `orchestrator.log`
- 口径：自然对照版（无整形）；判读以 `e2_precheck` 退出码为权威信号
