
<!-- records=480 cells=96 unstable=34 -->
### 采样量核算：`t1_ttft_ms`（目标：分辨 5% 的差异）

> **口径**：`可辨最小差异` = 以本单元实测离散度，两个同样大小的单元之间需要多大差异才会超出噪声尺度（√2·1.253·sd/√n）。它是**量级指示、不是显著性检验**（时延右偏）。离散度未知（n<2）的单元一律留 `—`，**不以 0 或当前 n 顶替**。

> ⚠ **两个「需 n≥」不是一回事，规划采样量要看后一个**：`需 n≥(平)` 是让目标差异**正好等于**噪声尺度的复测数——在那个 n 上，一个**真实存在**的目标差异只有**约五成**会被判为「超出噪声」（实测 52%~58%，n=5~40，D-201）；此前本段把这个数称作「足够」，**那是把抛硬币说成了保证**。`需 n≥(80%)` 才是「有 80% 把握看见它」所需的数，约为前者的 3.39 倍（判据是 |Δ|>噪声，故系数为 1+z=1.842；**不是**双侧显著性检验的 z₁₋α/₂+z₁₋β，那会多要 7.85 倍的外场工时，去买一个本报告从不作出的承诺）。

> ⚠ **两个「可辨最小差异」同理**：`(平)` 是**恰好等于**噪声尺度的差异——真有这么大的差异，也只有约五成会被判为「超出噪声」；`(80%)` 才是「这一格有 80% 把握分辨出来」的差异，约为前者的 1.842 倍。右侧「达标?」按 80% 判——**此前本表只印 `(平)` 那一个数，判词却按八成给**，一列按五成报、一列按八成判，并排放在同一行（D-240）。

| 单元 | n | 中位 | CV% | 超门? | 可辨最小差异(平) | 占中位(平) | 可辨最小差异(80%) | 达标?(80%) | 需 n≥(平) | 需 n≥(80%) |
|---|---|---|---|---|---|---|---|---|---|---|
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s1_chat | 15 | 453.8 | 4.3 | 达门 | 8.92 | 2% | 16.43 | 达标 | 3 | 8 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 15 | 453.1 | 12.4 | **✗超门** | 25.62 | 5.7% | 47.19 | ✗不足 | 20 | 66 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 14 | 441.3 | 3.9 | 达门 | 8.12 | 1.8% | 14.95 | 达标 | 2 | 7 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s1_chat | 14 | 438.25 | 4 | 达门 | 8.19 | 1.9% | 15.09 | 达标 | 2 | 7 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 13 | 449.98 | 11.4 | **✗超门** | 24.98 | 5.6% | 46 | ✗不足 | 17 | 55 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 15 | 431 | 5.1 | 达门 | 10 | 2.3% | 18.42 | 达标 | 4 | 11 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cucc · time_band=busy · tier=metro · profile_id=s1_chat | 13 | 462.9 | 5.2 | 达门 | 11.71 | 2.5% | 21.56 | 达标 | 4 | 12 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cucc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 15 | 457.33 | 13.5 | **✗超门**(场景内生) | 28.26 | 6.2% | 52.05 | ✗不足 | 23 | 78 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cucc · time_band=busy · tier=metro · profile_id=s3_multimodal | 11 | 451.9 | 3.9 | 达门 | 9.44 | 2.1% | 17.39 | 达标 | 2 | 7 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cucc · time_band=idle · tier=metro · profile_id=s1_chat | 14 | 441.6 | 3.2 | 达门 | 6.58 | 1.5% | 12.11 | 达标 | 2 | 5 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cucc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 12 | 466.79 | 10.1 | **✗超门**(场景内生) | 23.32 | 5% | 42.95 | ✗不足 | 12 | 41 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cucc · time_band=idle · tier=metro · profile_id=s3_multimodal | 13 | 443.5 | 3.7 | 达门 | 7.92 | 1.8% | 14.59 | 达标 | 2 | 6 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s1_chat | 14 | 466.8 | 3.8 | 达门 | 8.4 | 1.8% | 15.47 | 达标 | 2 | 7 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 15 | 464.55 | 7.2 | 达门 | 15.22 | 3.3% | 28.04 | ✗不足 | 7 | 22 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 13 | 476.8 | 3 | 达门 | 7.06 | 1.5% | 13 | 达标 | 2 | 4 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s1_chat | 13 | 437.3 | 3.7 | 达门 | 7.86 | 1.8% | 14.48 | 达标 | 2 | 6 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 15 | 432.34 | 16.5 | **✗超门**(场景内生) | 32.63 | 7.5% | 60.09 | ✗不足 | 35 | 116 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 15 | 438.5 | 5.4 | 达门 | 10.83 | 2.5% | 19.94 | 达标 | 4 | 13 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cucc · time_band=busy · tier=metro · profile_id=s1_chat | 14 | 456.2 | 4.4 | 达门 | 9.59 | 2.1% | 17.66 | 达标 | 3 | 9 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cucc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 14 | 443.18 | 10.5 | **✗超门**(场景内生) | 21.75 | 4.9% | 40.06 | ✗不足 | 14 | 46 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cucc · time_band=busy · tier=metro · profile_id=s3_multimodal | 15 | 464.7 | 3.5 | 达门 | 7.29 | 1.6% | 13.43 | 达标 | 2 | 6 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cucc · time_band=idle · tier=metro · profile_id=s1_chat | 14 | 445.95 | 3.7 | 达门 | 7.86 | 1.8% | 14.48 | 达标 | 2 | 6 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cucc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 14 | 463.96 | 14.1 | **✗超门**(场景内生) | 29.96 | 6.5% | 55.18 | ✗不足 | 24 | 80 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cucc · time_band=idle · tier=metro · profile_id=s3_multimodal | 15 | 453.9 | 4.4 | 达门 | 9.11 | 2% | 16.78 | 达标 | 3 | 9 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s1_chat | 15 | 468.2 | 3.6 | 达门 | 7.77 | 1.7% | 14.31 | 达标 | 2 | 6 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 13 | 409.14 | 11 | **✗超门**(场景内生) | 23.43 | 5.7% | 43.15 | ✗不足 | 18 | 58 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 15 | 463.1 | 4 | 达门 | 8.52 | 1.8% | 15.69 | 达标 | 3 | 7 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s1_chat | 13 | 452.8 | 2.8 | 达门 | 6.24 | 1.4% | 11.49 | 达标 | 1 | 4 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 14 | 458.99 | 12.7 | **✗超门**(场景内生) | 27.24 | 5.9% | 50.16 | ✗不足 | 20 | 67 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 14 | 448.7 | 4.8 | 达门 | 10.24 | 2.3% | 18.86 | 达标 | 3 | 10 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cucc · time_band=busy · tier=metro · profile_id=s1_chat | 13 | 481.3 | 3.9 | 达门 | 9.25 | 1.9% | 17.04 | 达标 | 2 | 7 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cucc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 14 | 475.75 | 13.1 | **✗超门**(场景内生) | 29.58 | 6.2% | 54.47 | ✗不足 | 22 | 74 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cucc · time_band=busy · tier=metro · profile_id=s3_multimodal | 15 | 475.3 | 4.7 | 达门 | 10.33 | 2.2% | 19.03 | 达标 | 3 | 10 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cucc · time_band=idle · tier=metro · profile_id=s1_chat | 13 | 468.2 | 4.8 | 达门 | 10.93 | 2.3% | 20.12 | 达标 | 3 | 10 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cucc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 15 | 455.67 | 8.6 | 达门 | 17.55 | 3.9% | 32.32 | ✗不足 | 9 | 31 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cucc · time_band=idle · tier=metro · profile_id=s3_multimodal | 15 | 447.7 | 4 | 达门 | 8.1 | 1.8% | 14.92 | 达标 | 2 | 7 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s1_chat | 14 | 498.15 | 21.2 | **✗超门** | 50.04 | 10% | 92.15 | ✗不足 | 57 | 192 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 12 | 415.33 | 26.1 | **✗超门** | 58.29 | 14% | 107.36 | ✗不足 | 95 | 321 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 13 | 447.1 | 27.4 | **✗超门** | 59.27 | 13.3% | 109.16 | ✗不足 | 92 | 310 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s1_chat | 13 | 452.9 | 25.6 | **✗超门** | 56.19 | 12.4% | 103.48 | ✗不足 | 81 | 272 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 15 | 443.79 | 17 | **✗超门** | 34.72 | 7.8% | 63.94 | ✗不足 | 37 | 125 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 15 | 414.6 | 21.7 | **✗超门** | 43.44 | 10.5% | 80.01 | ✗不足 | 66 | 224 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cucc · time_band=busy · tier=metro · profile_id=s1_chat | 14 | 497.8 | 28.2 | **✗超门** | 65.85 | 13.2% | 121.27 | ✗不足 | 98 | 333 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cucc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 14 | 512.31 | 17.5 | **✗超门** | 43.63 | 8.5% | 80.35 | ✗不足 | 41 | 138 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cucc · time_band=busy · tier=metro · profile_id=s3_multimodal | 13 | 509 | 16.6 | **✗超门** | 42.12 | 8.3% | 77.56 | ✗不足 | 36 | 121 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cucc · time_band=idle · tier=metro · profile_id=s1_chat | 13 | 427.4 | 15.3 | **✗超门** | 33.83 | 7.9% | 62.31 | ✗不足 | 33 | 111 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cucc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 13 | 407.76 | 26.8 | **✗超门** | 58.49 | 14.3% | 107.72 | ✗不足 | 107 | 363 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cucc · time_band=idle · tier=metro · profile_id=s3_multimodal | 15 | 471.5 | 17.9 | **✗超门** | 39.68 | 8.4% | 73.07 | ✗不足 | 43 | 145 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P05 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s1_chat | 13 | 479 | 3.5 | 达门 | 8.17 | 1.7% | 15.04 | 达标 | 2 | 6 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P05 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 14 | 466.3 | 11.9 | **✗超门**(场景内生) | 26.85 | 5.8% | 49.45 | ✗不足 | 19 | 63 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P05 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 15 | 489.4 | 5.1 | 达门 | 11.24 | 2.3% | 20.69 | 达标 | 4 | 11 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P05 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s1_chat | 15 | 451.6 | 4 | 达门 | 8.32 | 1.8% | 15.32 | 达标 | 3 | 7 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P05 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 15 | 428.87 | 9.9 | 达门 | 19.85 | 4.6% | 36.56 | ✗不足 | 13 | 44 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P05 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 15 | 442.1 | 4.1 | 达门 | 8.33 | 1.9% | 15.34 | 达标 | 3 | 8 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P05 · carrier=cucc · time_band=busy · tier=metro · profile_id=s1_chat | 13 | 501.3 | 4.1 | 达门 | 10.14 | 2% | 18.67 | 达标 | 3 | 8 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P05 · carrier=cucc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 14 | 497.4 | 13.7 | **✗超门**(场景内生) | 32.66 | 6.6% | 60.14 | ✗不足 | 25 | 82 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P05 · carrier=cucc · time_band=busy · tier=metro · profile_id=s3_multimodal | 15 | 495.1 | 4.1 | 达门 | 9.24 | 1.9% | 17.02 | 达标 | 3 | 8 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P05 · carrier=cucc · time_band=idle · tier=metro · profile_id=s1_chat | 14 | 465.25 | 3.6 | 达门 | 7.91 | 1.7% | 14.56 | 达标 | 2 | 6 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P05 · carrier=cucc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 14 | 463.65 | 9.4 | 达门 | 20.72 | 4.5% | 38.16 | ✗不足 | 12 | 38 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P05 · carrier=cucc · time_band=idle · tier=metro · profile_id=s3_multimodal | 14 | 467.1 | 5.2 | 达门 | 11.46 | 2.5% | 21.1 | 达标 | 4 | 12 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P06 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s1_chat | 15 | 487.4 | 4.4 | 达门 | 9.85 | 2% | 18.14 | 达标 | 3 | 9 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P06 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 14 | 490.87 | 8.3 | 达门 | 18.76 | 3.8% | 34.54 | ✗不足 | 9 | 28 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P06 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 14 | 494.2 | 4.5 | 达门 | 10.49 | 2.1% | 19.32 | 达标 | 3 | 9 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P06 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s1_chat | 14 | 460.65 | 5.6 | 达门 | 12.18 | 2.6% | 22.42 | 达标 | 4 | 14 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P06 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 12 | 455.1 | 14.1 | **✗超门**(场景内生) | 32.97 | 7.2% | 60.71 | ✗不足 | 26 | 86 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P06 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 13 | 462.2 | 6.5 | 达门 | 14.79 | 3.2% | 27.24 | ✗不足 | 6 | 19 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P06 · carrier=cucc · time_band=busy · tier=metro · profile_id=s1_chat | 15 | 505.1 | 3.4 | 达门 | 7.79 | 1.5% | 14.35 | 达标 | 2 | 5 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P06 · carrier=cucc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 15 | 491.27 | 10.3 | **✗超门**(场景内生) | 23.13 | 4.7% | 42.59 | ✗不足 | 14 | 46 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P06 · carrier=cucc · time_band=busy · tier=metro · profile_id=s3_multimodal | 15 | 507.6 | 3.4 | 达门 | 7.79 | 1.5% | 14.34 | 达标 | 2 | 5 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P06 · carrier=cucc · time_band=idle · tier=metro · profile_id=s1_chat | 13 | 470.7 | 4.1 | 达门 | 9.43 | 2% | 17.37 | 达标 | 3 | 8 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P06 · carrier=cucc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 15 | 482.66 | 11.2 | **✗超门**(场景内生) | 25.01 | 5.2% | 46.07 | ✗不足 | 17 | 55 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P06 · carrier=cucc · time_band=idle · tier=metro · profile_id=s3_multimodal | 15 | 474.3 | 5.1 | 达门 | 10.88 | 2.3% | 20.03 | 达标 | 4 | 11 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P07 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s1_chat | 15 | 491.2 | 3.9 | 达门 | 8.87 | 1.8% | 16.33 | 达标 | 2 | 7 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P07 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 13 | 465.71 | 14.6 | **✗超门**(场景内生) | 33.7 | 7.2% | 62.06 | ✗不足 | 28 | 93 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P07 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 14 | 498.4 | 5.5 | 达门 | 12.84 | 2.6% | 23.64 | 达标 | 4 | 13 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P07 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s1_chat | 13 | 470.9 | 4.3 | 达门 | 9.93 | 2.1% | 18.28 | 达标 | 3 | 8 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P07 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 14 | 442.78 | 13.7 | **✗超门**(场景内生) | 28.98 | 6.5% | 53.36 | ✗不足 | 24 | 82 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P07 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 13 | 469.8 | 4.5 | 达门 | 10.28 | 2.2% | 18.93 | 达标 | 3 | 9 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P07 · carrier=cucc · time_band=busy · tier=metro · profile_id=s1_chat | 15 | 489.1 | 6.3 | 达门 | 14.06 | 2.9% | 25.9 | ✗不足 | 5 | 17 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P07 · carrier=cucc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 15 | 525.21 | 14.6 | **✗超门**(场景内生) | 34.15 | 6.5% | 62.9 | ✗不足 | 26 | 87 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P07 · carrier=cucc · time_band=busy · tier=metro · profile_id=s3_multimodal | 14 | 501.3 | 5.4 | 达门 | 12.74 | 2.5% | 23.47 | 达标 | 4 | 13 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P07 · carrier=cucc · time_band=idle · tier=metro · profile_id=s1_chat | 15 | 480.4 | 3.9 | 达门 | 8.42 | 1.8% | 15.51 | 达标 | 2 | 7 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P07 · carrier=cucc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 14 | 439.84 | 13.5 | **✗超门**(场景内生) | 29.6 | 6.7% | 54.52 | ✗不足 | 26 | 87 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P07 · carrier=cucc · time_band=idle · tier=metro · profile_id=s3_multimodal | 14 | 464.2 | 3.6 | 达门 | 7.83 | 1.7% | 14.41 | 达标 | 2 | 6 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P08 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s1_chat | 14 | 542.15 | 4.3 | 达门 | 11.06 | 2% | 20.38 | 达标 | 3 | 8 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P08 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 15 | 518.91 | 13.2 | **✗超门**(场景内生) | 31.18 | 6% | 57.41 | ✗不足 | 22 | 74 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P08 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 14 | 539.95 | 4.8 | 达门 | 12.16 | 2.3% | 22.4 | 达标 | 3 | 10 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P08 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s1_chat | 15 | 487.7 | 3.4 | 达门 | 7.58 | 1.6% | 13.95 | 达标 | 2 | 5 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P08 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 15 | 523.29 | 13.6 | **✗超门**(场景内生) | 32.34 | 6.2% | 59.55 | ✗不足 | 23 | 78 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P08 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 15 | 495.7 | 4.4 | 达门 | 10.01 | 2% | 18.43 | 达标 | 3 | 9 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P08 · carrier=cucc · time_band=busy · tier=metro · profile_id=s1_chat | 15 | 562.5 | 6.8 | 达门 | 17.62 | 3.1% | 32.46 | ✗不足 | 6 | 20 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P08 · carrier=cucc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 15 | 536.61 | 7.9 | 达门 | 20.09 | 3.7% | 36.99 | ✗不足 | 9 | 29 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P08 · carrier=cucc · time_band=busy · tier=metro · profile_id=s3_multimodal | 13 | 560 | 4.2 | 达门 | 11.53 | 2.1% | 21.24 | 达标 | 3 | 8 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P08 · carrier=cucc · time_band=idle · tier=metro · profile_id=s1_chat | 15 | 513.1 | 5 | 达门 | 11.72 | 2.3% | 21.58 | 达标 | 4 | 11 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P08 · carrier=cucc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 13 | 530.61 | 16.8 | **✗超门**(场景内生) | 42.43 | 8% | 78.14 | ✗不足 | 34 | 113 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P08 · carrier=cucc · time_band=idle · tier=metro · profile_id=s3_multimodal | 15 | 499.3 | 4.1 | 达门 | 9.35 | 1.9% | 17.22 | 达标 | 3 | 8 |

> **结论**：43/96 个单元在当前 n 下**没有 80% 的把握**看见 5% 的差异；这些单元的建议复测数中位为 **n≥111**（每侧）——**该中位只汇网络侧的 23 个**，已排除 20 个 `SCENARIO_INTRINSIC_JITTER` 单元。 其中 **12 个**单元的当前 n 恰好落在「差异等于噪声尺度」附近——**那只有约五成把握**，不要据此认为采样量已经够了。

> ⚠ **另有 20 个单元标 `SCENARIO_INTRINSIC_JITTER`**（其 `需 n≥` 中位 **78**，**单列，不并入上句**）。它们超门的那部分方差**不在链路上**（D-372：同批 RTT 平稳、TTFT~RTT 相关 0.00），**照这个数加外场 run 买不到网络精度**。要降它只有两条路：改**场景/服务端侧**的测量装置，或对该 KPI **放宽 MDE 目标**并写明理由。

> ⚠ 其中 **34 个单元 CV 已超门**（标 `✗超门`）。对这些单元,`需 n≥` 只是把噪声摊薄的算术,**不解决它们本身不可重复**——先查原因(设备/环境/场景本身不稳)再重采,不要照着这个数字硬加复测。
exit=0
