
<!-- records=480 cells=96 unstable=12 -->
### 采样量核算：`n1_rtt_p50_ms`（目标：分辨 5% 的差异）

> **口径**：`可辨最小差异` = 以本单元实测离散度，两个同样大小的单元之间需要多大差异才会超出噪声尺度（√2·1.253·sd/√n）。它是**量级指示、不是显著性检验**（时延右偏）。离散度未知（n<2）的单元一律留 `—`，**不以 0 或当前 n 顶替**。

> ⚠ **两个「需 n≥」不是一回事，规划采样量要看后一个**：`需 n≥(平)` 是让目标差异**正好等于**噪声尺度的复测数——在那个 n 上，一个**真实存在**的目标差异只有**约五成**会被判为「超出噪声」（实测 52%~58%，n=5~40，D-201）；此前本段把这个数称作「足够」，**那是把抛硬币说成了保证**。`需 n≥(80%)` 才是「有 80% 把握看见它」所需的数，约为前者的 3.39 倍（判据是 |Δ|>噪声，故系数为 1+z=1.842；**不是**双侧显著性检验的 z₁₋α/₂+z₁₋β，那会多要 7.85 倍的外场工时，去买一个本报告从不作出的承诺）。

> ⚠ **两个「可辨最小差异」同理**：`(平)` 是**恰好等于**噪声尺度的差异——真有这么大的差异，也只有约五成会被判为「超出噪声」；`(80%)` 才是「这一格有 80% 把握分辨出来」的差异，约为前者的 1.842 倍。右侧「达标?」按 80% 判——**此前本表只印 `(平)` 那一个数，判词却按八成给**，一列按五成报、一列按八成判，并排放在同一行（D-240）。

| 单元 | n | 中位 | CV% | 超门? | 可辨最小差异(平) | 占中位(平) | 可辨最小差异(80%) | 达标?(80%) | 需 n≥(平) | 需 n≥(80%) |
|---|---|---|---|---|---|---|---|---|---|---|
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s1_chat | 15 | 21.8 | 6.9 | 达门 | 0.68 | 3.1% | 1.25 | ✗不足 | 6 | 20 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 15 | 21.8 | 6.9 | 达门 | 0.68 | 3.1% | 1.25 | ✗不足 | 6 | 20 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 14 | 21.34 | 6.8 | 达门 | 0.69 | 3.2% | 1.26 | ✗不足 | 6 | 20 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s1_chat | 14 | 15.98 | 7.6 | 达门 | 0.57 | 3.6% | 1.06 | ✗不足 | 8 | 25 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 13 | 15.25 | 7.6 | 达门 | 0.59 | 3.9% | 1.09 | ✗不足 | 8 | 27 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 15 | 16.65 | 7.4 | 达门 | 0.54 | 3.2% | 0.99 | ✗不足 | 7 | 22 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cucc · time_band=busy · tier=metro · profile_id=s1_chat | 13 | 25.2 | 5.9 | 达门 | 0.71 | 2.8% | 1.3 | ✗不足 | 5 | 14 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cucc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 15 | 25.2 | 5.9 | 达门 | 0.66 | 2.6% | 1.21 | 达标 | 5 | 14 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cucc · time_band=busy · tier=metro · profile_id=s3_multimodal | 11 | 23.86 | 5.8 | 达门 | 0.75 | 3.2% | 1.39 | ✗不足 | 5 | 15 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cucc · time_band=idle · tier=metro · profile_id=s1_chat | 14 | 18.55 | 6.5 | 达门 | 0.56 | 3% | 1.03 | ✗不足 | 6 | 18 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cucc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 12 | 17.88 | 6.8 | 达门 | 0.62 | 3.5% | 1.14 | ✗不足 | 6 | 20 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P01 · carrier=cucc · time_band=idle · tier=metro · profile_id=s3_multimodal | 13 | 18.7 | 6.6 | 达门 | 0.58 | 3.1% | 1.08 | ✗不足 | 6 | 18 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s1_chat | 14 | 24.93 | 1.9 | 达门 | 0.22 | 0.9% | 0.41 | 达标 | 1 | 2 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 15 | 25.08 | 2.3 | 达门 | 0.27 | 1.1% | 0.49 | 达标 | 1 | 3 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 13 | 25.25 | 2.4 | 达门 | 0.29 | 1.2% | 0.54 | 达标 | 1 | 3 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s1_chat | 13 | 18.61 | 1.9 | 达门 | 0.17 | 0.9% | 0.31 | 达标 | 1 | 2 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 15 | 18.47 | 1.7 | 达门 | 0.15 | 0.8% | 0.27 | 达标 | 1 | 2 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 15 | 18.47 | 1.7 | 达门 | 0.15 | 0.8% | 0.27 | 达标 | 1 | 2 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cucc · time_band=busy · tier=metro · profile_id=s1_chat | 14 | 28.07 | 2.3 | 达门 | 0.3 | 1.1% | 0.55 | 达标 | 1 | 3 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cucc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 14 | 28.02 | 2.3 | 达门 | 0.3 | 1.1% | 0.56 | 达标 | 1 | 3 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cucc · time_band=busy · tier=metro · profile_id=s3_multimodal | 15 | 28.07 | 2.2 | 达门 | 0.28 | 1% | 0.52 | 达标 | 1 | 3 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cucc · time_band=idle · tier=metro · profile_id=s1_chat | 14 | 20.87 | 1.9 | 达门 | 0.19 | 0.9% | 0.35 | 达标 | 1 | 2 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cucc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 14 | 20.82 | 2.3 | 达门 | 0.23 | 1.1% | 0.42 | 达标 | 1 | 3 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P02 · carrier=cucc · time_band=idle · tier=metro · profile_id=s3_multimodal | 15 | 20.83 | 2.3 | 达门 | 0.22 | 1.1% | 0.4 | 达标 | 1 | 3 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s1_chat | 15 | 27.34 | 2.7 | 达门 | 0.34 | 1.2% | 0.63 | 达标 | 1 | 4 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 13 | 27.34 | 2.7 | 达门 | 0.36 | 1.3% | 0.66 | 达标 | 1 | 4 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 15 | 27.34 | 2.7 | 达门 | 0.34 | 1.2% | 0.63 | 达标 | 1 | 4 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s1_chat | 13 | 20.11 | 2.6 | 达门 | 0.26 | 1.3% | 0.48 | 达标 | 1 | 3 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 14 | 20.05 | 2.5 | 达门 | 0.24 | 1.2% | 0.44 | 达标 | 1 | 3 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 14 | 19.94 | 2.5 | 达门 | 0.23 | 1.2% | 0.43 | 达标 | 1 | 3 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cucc · time_band=busy · tier=metro · profile_id=s1_chat | 13 | 30.95 | 2 | 达门 | 0.31 | 1% | 0.56 | 达标 | 1 | 2 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cucc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 14 | 30.94 | 1.9 | 达门 | 0.28 | 0.9% | 0.52 | 达标 | 1 | 2 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cucc · time_band=busy · tier=metro · profile_id=s3_multimodal | 15 | 30.93 | 2.1 | 达门 | 0.3 | 1% | 0.54 | 达标 | 1 | 2 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cucc · time_band=idle · tier=metro · profile_id=s1_chat | 13 | 22.54 | 2.2 | 达门 | 0.24 | 1.1% | 0.44 | 达标 | 1 | 2 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cucc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 15 | 22.5 | 2 | 达门 | 0.21 | 0.9% | 0.38 | 达标 | 1 | 2 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P03 · carrier=cucc · time_band=idle · tier=metro · profile_id=s3_multimodal | 15 | 22.5 | 2 | 达门 | 0.21 | 0.9% | 0.38 | 达标 | 1 | 2 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s1_chat | 14 | 27.04 | 11.6 | **✗超门** | 1.53 | 5.7% | 2.82 | ✗不足 | 19 | 62 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 12 | 27.8 | 10.8 | **✗超门** | 1.55 | 5.6% | 2.86 | ✗不足 | 15 | 51 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 13 | 28.28 | 11.2 | **✗超门** | 1.57 | 5.5% | 2.89 | ✗不足 | 17 | 55 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s1_chat | 13 | 20.01 | 16.1 | **✗超门** | 1.63 | 8.1% | 3 | ✗不足 | 35 | 117 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 15 | 20.01 | 15.5 | **✗超门** | 1.46 | 7.3% | 2.68 | ✗不足 | 32 | 108 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 15 | 20.01 | 15.5 | **✗超门** | 1.46 | 7.3% | 2.68 | ✗不足 | 32 | 108 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cucc · time_band=busy · tier=metro · profile_id=s1_chat | 14 | 32.71 | 11.2 | **✗超门** | 1.71 | 5.2% | 3.15 | ✗不足 | 16 | 52 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cucc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 14 | 32.65 | 11.2 | **✗超门** | 1.68 | 5.2% | 3.1 | ✗不足 | 15 | 51 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cucc · time_band=busy · tier=metro · profile_id=s3_multimodal | 13 | 32.59 | 11.7 | **✗超门** | 1.83 | 5.6% | 3.36 | ✗不足 | 17 | 56 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cucc · time_band=idle · tier=metro · profile_id=s1_chat | 13 | 23.06 | 13.8 | **✗超门** | 1.52 | 6.6% | 2.8 | ✗不足 | 23 | 77 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cucc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 13 | 23.34 | 12.9 | **✗超门** | 1.45 | 6.2% | 2.67 | ✗不足 | 20 | 68 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P04 · carrier=cucc · time_band=idle · tier=metro · profile_id=s3_multimodal | 15 | 23.06 | 12.9 | **✗超门** | 1.32 | 5.7% | 2.43 | ✗不足 | 20 | 67 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P05 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s1_chat | 13 | 31.54 | 1.7 | 达门 | 0.26 | 0.8% | 0.48 | 达标 | 1 | 2 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P05 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 14 | 31.53 | 1.6 | 达门 | 0.25 | 0.8% | 0.45 | 达标 | 1 | 2 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P05 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 15 | 31.52 | 1.7 | 达门 | 0.25 | 0.8% | 0.46 | 达标 | 1 | 2 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P05 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s1_chat | 15 | 23.05 | 2.3 | 达门 | 0.24 | 1.1% | 0.45 | 达标 | 1 | 3 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P05 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 15 | 23.05 | 2.3 | 达门 | 0.24 | 1.1% | 0.45 | 达标 | 1 | 3 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P05 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 15 | 23.05 | 2.3 | 达门 | 0.24 | 1.1% | 0.45 | 达标 | 1 | 3 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P05 · carrier=cucc · time_band=busy · tier=metro · profile_id=s1_chat | 13 | 35.01 | 2.2 | 达门 | 0.38 | 1.1% | 0.7 | 达标 | 1 | 3 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P05 · carrier=cucc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 14 | 35.08 | 2.1 | 达门 | 0.35 | 1% | 0.65 | 达标 | 1 | 2 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P05 · carrier=cucc · time_band=busy · tier=metro · profile_id=s3_multimodal | 15 | 35.01 | 2.1 | 达门 | 0.33 | 1% | 0.61 | 达标 | 1 | 2 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P05 · carrier=cucc · time_band=idle · tier=metro · profile_id=s1_chat | 14 | 26.11 | 2.7 | 达门 | 0.34 | 1.3% | 0.62 | 达标 | 1 | 4 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P05 · carrier=cucc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 14 | 26.11 | 2.7 | 达门 | 0.34 | 1.3% | 0.62 | 达标 | 1 | 4 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P05 · carrier=cucc · time_band=idle · tier=metro · profile_id=s3_multimodal | 14 | 26.11 | 2.4 | 达门 | 0.29 | 1.1% | 0.54 | 达标 | 1 | 3 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P06 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s1_chat | 15 | 33.55 | 2.3 | 达门 | 0.35 | 1.1% | 0.65 | 达标 | 1 | 3 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P06 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 14 | 33.6 | 2.4 | 达门 | 0.38 | 1.1% | 0.7 | 达标 | 1 | 3 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P06 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 14 | 33.6 | 2.4 | 达门 | 0.38 | 1.1% | 0.69 | 达标 | 1 | 3 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P06 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s1_chat | 14 | 24.56 | 2.7 | 达门 | 0.31 | 1.3% | 0.58 | 达标 | 1 | 4 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P06 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 12 | 24.56 | 2.6 | 达门 | 0.33 | 1.3% | 0.61 | 达标 | 1 | 3 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P06 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 13 | 24.59 | 2.7 | 达门 | 0.33 | 1.3% | 0.61 | 达标 | 1 | 4 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P06 · carrier=cucc · time_band=busy · tier=metro · profile_id=s1_chat | 15 | 37.47 | 2.5 | 达门 | 0.43 | 1.1% | 0.79 | 达标 | 1 | 3 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P06 · carrier=cucc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 15 | 37.47 | 2.5 | 达门 | 0.43 | 1.1% | 0.79 | 达标 | 1 | 3 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P06 · carrier=cucc · time_band=busy · tier=metro · profile_id=s3_multimodal | 15 | 37.47 | 2.5 | 达门 | 0.43 | 1.1% | 0.79 | 达标 | 1 | 3 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P06 · carrier=cucc · time_band=idle · tier=metro · profile_id=s1_chat | 13 | 27.86 | 1.9 | 达门 | 0.26 | 0.9% | 0.47 | 达标 | 1 | 2 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P06 · carrier=cucc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 15 | 27.86 | 2.1 | 达门 | 0.26 | 0.9% | 0.48 | 达标 | 1 | 2 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P06 · carrier=cucc · time_band=idle · tier=metro · profile_id=s3_multimodal | 15 | 27.86 | 2.1 | 达门 | 0.26 | 0.9% | 0.48 | 达标 | 1 | 2 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P07 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s1_chat | 15 | 34.3 | 6.7 | 达门 | 1.02 | 3% | 1.88 | ✗不足 | 6 | 18 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P07 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 13 | 34.3 | 6.5 | 达门 | 1.06 | 3.1% | 1.96 | ✗不足 | 6 | 17 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P07 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 14 | 33.43 | 6.8 | 达门 | 1.07 | 3.2% | 1.98 | ✗不足 | 6 | 20 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P07 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s1_chat | 13 | 25.74 | 6.4 | 达门 | 0.78 | 3% | 1.44 | ✗不足 | 5 | 17 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P07 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 14 | 24.78 | 6.4 | 达门 | 0.75 | 3% | 1.38 | ✗不足 | 6 | 18 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P07 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 13 | 23.83 | 6.7 | 达门 | 0.82 | 3.4% | 1.51 | ✗不足 | 7 | 21 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P07 · carrier=cucc · time_band=busy · tier=metro · profile_id=s1_chat | 15 | 39.25 | 6.7 | 达门 | 1.15 | 2.9% | 2.12 | ✗不足 | 6 | 18 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P07 · carrier=cucc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 15 | 39.25 | 6.7 | 达门 | 1.15 | 2.9% | 2.12 | ✗不足 | 6 | 18 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P07 · carrier=cucc · time_band=busy · tier=metro · profile_id=s3_multimodal | 14 | 39.45 | 6.3 | 达门 | 1.14 | 2.9% | 2.09 | ✗不足 | 5 | 16 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P07 · carrier=cucc · time_band=idle · tier=metro · profile_id=s1_chat | 15 | 28.79 | 7.6 | 达门 | 0.99 | 3.4% | 1.82 | ✗不足 | 8 | 25 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P07 · carrier=cucc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 14 | 28.39 | 7.9 | 达门 | 1.06 | 3.7% | 1.95 | ✗不足 | 8 | 27 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P07 · carrier=cucc · time_band=idle · tier=metro · profile_id=s3_multimodal | 14 | 27.73 | 7.7 | 达门 | 1.03 | 3.7% | 1.9 | ✗不足 | 8 | 27 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P08 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s1_chat | 14 | 49.8 | 2.4 | 达门 | 0.56 | 1.1% | 1.03 | 达标 | 1 | 3 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P08 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 15 | 49.73 | 2.5 | 达门 | 0.57 | 1.1% | 1.05 | 达标 | 1 | 3 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P08 · carrier=cmcc · time_band=busy · tier=metro · profile_id=s3_multimodal | 14 | 49.61 | 2.5 | 达门 | 0.58 | 1.2% | 1.08 | 达标 | 1 | 3 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P08 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s1_chat | 15 | 36.92 | 1.9 | 达门 | 0.33 | 0.9% | 0.6 | 达标 | 1 | 2 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P08 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 15 | 36.92 | 1.9 | 达门 | 0.33 | 0.9% | 0.6 | 达标 | 1 | 2 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P08 · carrier=cmcc · time_band=idle · tier=metro · profile_id=s3_multimodal | 15 | 36.92 | 1.9 | 达门 | 0.33 | 0.9% | 0.6 | 达标 | 1 | 2 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P08 · carrier=cucc · time_band=busy · tier=metro · profile_id=s1_chat | 15 | 56.31 | 3 | 达门 | 0.79 | 1.4% | 1.45 | 达标 | 2 | 4 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P08 · carrier=cucc · time_band=busy · tier=metro · profile_id=s2_coding_agent | 15 | 56.31 | 3 | 达门 | 0.79 | 1.4% | 1.45 | 达标 | 2 | 4 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P08 · carrier=cucc · time_band=busy · tier=metro · profile_id=s3_multimodal | 13 | 57.05 | 2.9 | 达门 | 0.81 | 1.4% | 1.5 | 达标 | 2 | 4 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P08 · carrier=cucc · time_band=idle · tier=metro · profile_id=s1_chat | 15 | 41.42 | 2.3 | 达门 | 0.43 | 1% | 0.78 | 达标 | 1 | 3 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P08 · carrier=cucc · time_band=idle · tier=metro · profile_id=s2_coding_agent | 13 | 41.52 | 2.3 | 达门 | 0.47 | 1.1% | 0.87 | 达标 | 1 | 3 |
| campaign_id=SYNTH-EXP · point_id=SYNTH-P08 · carrier=cucc · time_band=idle · tier=metro · profile_id=s3_multimodal | 15 | 41.42 | 2.3 | 达门 | 0.43 | 1% | 0.78 | 达标 | 1 | 3 |

> **结论**：35/96 个单元在当前 n 下**没有 80% 的把握**看见 5% 的差异；这些单元的建议复测数中位为 **n≥22**（每侧）。 其中 **23 个**单元的当前 n 恰好落在「差异等于噪声尺度」附近——**那只有约五成把握**，不要据此认为采样量已经够了。

> ⚠ 其中 **12 个单元 CV 已超门**（标 `✗超门`）。对这些单元,`需 n≥` 只是把噪声摊薄的算术,**不解决它们本身不可重复**——先查原因(设备/环境/场景本身不稳)再重采,不要照着这个数字硬加复测。
exit=0
