package com.aneb.probe.engine

import com.aneb.probe.data.ScenarioResultEntity
import com.aneb.probe.data.TestRun
import com.aneb.probe.scoring.AqsScorer
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.add
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray

/**
 * 结果上报体构造（P1 范围 8，设计文档 §7 上报口径）。纯 JVM、无 Android 依赖。
 *
 * 合同字段（server/handlers_results.go 校验）：claim_scope（const 锁定）、kpi_set、
 * aqs_version、profile_versions、schema_version 顶层必填。正文＝TestRun 摘要 +
 * 各场景 KPI（值+分级+三态+原因码）+ ITL 对数分桶直方图；目标 <200KB。
 */
object ResultReporter {

    const val CLAIM_SCOPE = "application_end_to_end_to_probe_node"
    const val SCHEMA_VERSION = "1.0"

    /** 上报体大小软上限（bytes）；超限由调用方打 REPORT_SIZE_WARN 日志 */
    const val MAX_REPORT_BYTES = 200_000

    fun build(
        run: TestRun,
        scenarios: List<Pair<ScenarioResultEntity, ItlHistogram>>,
        aqs: AqsScorer.AqsResult,
        /**
         * v0.2 并列出分（阶段二，D-26）：非 null 时**附加**写入 `run.aqs_v02`（含 C1/C2 子分），
         * 供结果页展示真实 v0.2「组→KPI→贡献分」。纯 additive——不改 `run.aqs`(v0.1 主分)语义，
         * 服务端 validateResultContract 只校验必填字段、不拒新增字段（已读码确认）。
         */
        aqsV02: AqsScorer.AqsResult? = null,
        /**
         * Token 模式并列出分（Profile 框架 §2.5，additive）：非 null 时**附加**写入 `run.aqs_token`
         * （分数/子分/权重表 id + 工作量数值块，纯数据不落文案——facet4 结论由 UI 从落库子分派生，
         * D-02 不重算打分）。D1 缺失（当前 profile 集无 download_burst）时诚实记
         * not_computable_reason=KPI_MISSING:D1，download_burst 接入后自愈出分。
         */
        aqsToken: AqsScorer.AqsResult? = null,
        tokenWeightsTableId: String? = null,
        tokenWorkload: com.aneb.probe.scoring.TokenBehaviorClassifier.WorkloadSignal? = null,
        /** S1 会话完成率（D-33 实测；null 值=无遍数据不写字段，R-10）。 */
        tokenS1: com.aneb.probe.scoring.KpiValue? = null,
        /**
         * run 级环境摘要（THERMAL 接线，D-556；同构先例 skipped_profiles/D-534）：非 null 时
         * **附加**写入 `run.env`（thermal_max_status + thermal_polluting_event_count，双键恒在）。
         * 块缺席=该 run 早于本字段上线；双 null=无热监控；"none"+0=监控在位且全程干净
         * （0 是真实读数，非 R-10 伪装）。纯 additive，老语料照常过 schema。
         */
        env: ThermalSummary.Env? = null,
        /**
         * run 级 voice 摘要（大脑 08-22 裁定 voice 半；挂接先例 AqsV02Gate/D-26，窗口与选择在
         * [VoiceSummary]）：非 null 时**附加**写入 `run.voice`（六键恒在，各值按 voice_result
         * 实体语义独立可空，R-10 原样透传；ts_epoch_ms=溯源，跨纪元以它为准，D-513）。
         * 块缺席=24h 窗内无 Done 行或 run 早于本字段上线。边界：摘要只供战役报告链并入与
         * 横幅计数，不得作判读源（scripts/README「语音双通道边界」同文）。
         */
        voice: VoiceSummary.Voice? = null,
    ): String = buildJsonObject {
        // ---- 合同字段（顶层，const/枚举锁定） ----
        put("claim_scope", CLAIM_SCOPE)
        put("kpi_set", run.kpiSet)
        put("aqs_version", run.aqsVersion)
        put("profile_versions", run.profileVersions)
        put("schema_version", SCHEMA_VERSION)

        // ---- TestRun 摘要 ----
        put("run", buildJsonObject {
            put("run_id", run.runId)
            put("started_at_epoch_ms", run.startedAtEpochMs)
            put("mode", run.mode)
            put("scenario_order", run.scenarioOrder)
            put("transport", run.transport)
            put("profile_source", run.profileSource)
            put("app_version_name", run.appVersionName)
            put("app_version_code", run.appVersionCode)
            put("guard_metadata", run.guardMetadata)
            put("status", run.status)
            // D-534 §2：键缺席=该 run 早于本字段上线（R-10 缺失≠空数组），""→[]=明确零跳过。
            run.skippedProfiles?.let { csv ->
                putJsonArray("skipped_profiles") {
                    csv.split(',').map { it.trim() }.filter { it.isNotEmpty() }.forEach { add(it) }
                }
            }
            // THERMAL 接线（D-556，additive）：块缺席=早于上线；双 null=无监控；"none"+0=在位且干净。
            // String?/Int? 的 null → JsonNull（not_computable_reason 同款先例），两键块内恒在。
            if (env != null) {
                put("env", buildJsonObject {
                    put("thermal_max_status", env.thermalMaxStatus)
                    put("thermal_polluting_event_count", env.thermalPollutingCount)
                })
            }
            // voice 摘要（大脑 08-22 裁定，additive）：六键恒在块内，值按实体语义独立可空（R-10）。
            if (voice != null) {
                put("voice", buildJsonObject {
                    put("caliber", voice.caliber)
                    put("m7_max_frame_gap_ms", voice.m7MaxFrameGapMs)
                    put("mouth_ear_proxy_p50_ms", voice.mouthEarProxyP50Ms)
                    put("low_confidence", voice.lowConfidence)
                    put("turns_ok", voice.turnsOk)
                    put("ts_epoch_ms", voice.tsEpochMs)
                })
            }
            put("aqs", buildJsonObject {
                put("score", aqs.score)
                put("low_confidence", aqs.lowConfidence)
                put("veto_applied", aqs.vetoApplied)
                put("not_computable_reason", aqs.notComputableReason)
                put("input_mapping", AqsInputMapper.MAPPING_DESCRIPTION)
                put("sub_scores", buildJsonObject {
                    aqs.subScores.forEach { (k, v) -> put(k, v) }
                })
            })
            // v0.2 并列出分（D-26，additive）：仅当有可用 continuity 数据时写入；含 C1/C2 子分
            if (aqsV02 != null) {
                put("aqs_v02", buildJsonObject {
                    put("aqs_version", aqsV02.aqsVersion)
                    put("score", aqsV02.score)
                    put("low_confidence", aqsV02.lowConfidence)
                    put("veto_applied", aqsV02.vetoApplied)
                    put("not_computable_reason", aqsV02.notComputableReason)
                    put("sub_scores", buildJsonObject {
                        aqsV02.subScores.forEach { (k, v) -> put(k, v) }
                    })
                })
            }
            // Token 模式并列出分（D-29，additive）：分数/子分/权重表 + 工作量数值块（facet4 输入 A）。
            // 纯数据合同——行为特征/建议文案由 UI 从这些落库数据派生（D-02 不重算），不冻结进档。
            if (aqsToken != null) {
                put("aqs_token", buildJsonObject {
                    put("aqs_version", aqsToken.aqsVersion)
                    put("score", aqsToken.score)
                    put("low_confidence", aqsToken.lowConfidence)
                    put("veto_applied", aqsToken.vetoApplied)
                    put("not_computable_reason", aqsToken.notComputableReason)
                    put("weights_table_id", tokenWeightsTableId)
                    // S1 完成率外显（D-33）：值+轮数+低置信+否决标——让 S1 否决在结果页可解释
                    put("s1_veto_applied", aqsToken.s1VetoApplied)
                    if (tokenS1?.value != null) {
                        put("s1_session_success_rate", tokenS1.value)
                        put("s1_rounds", tokenS1.sampleCount)
                        put("s1_low_confidence", tokenS1.lowConfidence)
                    }
                    put("sub_scores", buildJsonObject {
                        aqsToken.subScores.forEach { (k, v) -> put(k, v) }
                    })
                    if (tokenWorkload != null) {
                        put("workload", buildJsonObject {
                            put("uplink_bytes_per_round", tokenWorkload.uplinkBytesPerRound)
                            put("peak_to_mean_ratio", tokenWorkload.peakToMeanRatio)
                            put("downlink_media_bytes", tokenWorkload.downlinkMediaBytes)
                            put("token_stream_len", tokenWorkload.tokenStreamLen)
                            put("tool_loop_rounds", tokenWorkload.toolLoopRounds)
                            put("has_think_pause", tokenWorkload.hasThinkPause)
                            put("short_context_multi_turn", tokenWorkload.shortContextMultiTurn)
                            put("long_stream_or_continuous", tokenWorkload.longStreamOrContinuous)
                        })
                    }
                })
            }
        })

        // ---- 各场景 KPI + ITL 直方图 ----
        putJsonArray("scenarios") {
            for ((s, hist) in scenarios) add(scenarioJson(s, hist))
        }
    }.toString()

    private fun scenarioJson(s: ScenarioResultEntity, hist: ItlHistogram): JsonObject = buildJsonObject {
        put("profile_id", s.profileId)
        put("profile_version", s.profileVersion)
        put("repeat_index", s.repeatIndex)
        put("order_index", s.orderIndex)
        put("validity", s.validity)
        put("invalid_reasons", s.invalidReasons)
        put("kpi", buildJsonObject {
            put("t1_ttft_ms", s.t1TtftMs); put("t1_grade", s.t1Grade)
            put("t2_itl_p95_ms", s.t2ItlP95Ms); put("t2_grade", s.t2Grade)
            put("t2_itl_p95_incl_coalesced_ms", s.t2ItlP95InclCoalescedMs)
            put("t3_stall_rate", s.t3StallRate); put("t3_grade", s.t3Grade)
            put("t3_stall_rate_incl_resume", s.t3StallRateInclResume)
            put("t4_severe_stall_rate", s.t4SevereStallRate); put("t4_grade", s.t4Grade)
            put("t5_resume_p95_ms", s.t5ResumeP95Ms)
            put("n1_rtt_p50_ms", s.n1RttP50Ms); put("n1_grade", s.n1Grade)
            put("n2_jitter_ms", s.n2JitterMs); put("n2_grade", s.n2Grade)
            put("u1_goodput_mbps", s.u1GoodputMbps); put("u1_grade", s.u1Grade)
            put("u1_goodput_excl_slow_start_mbps", s.u1GoodputExclSlowStartMbps)
            put("u2_tool_loop_p95_ms", s.u2ToolLoopP95Ms); put("u2_grade", s.u2Grade)
            // T47 批①（D-468/D-469）：D1 半成品补齐——KpiCalculator 早算出却从未上线的字段
            put("d1_goodput_mbps", s.d1GoodputMbps); put("d1_grade", s.d1Grade)
            // T47 批③（D-468/D-469）：U3/D3 单流自适应窗口 goodput 探针，spec §8.4.2 全字段
            put("u3_goodput_mbps", s.u3GoodputMbps); put("u3_grade", s.u3Grade)
            put("u3_goodput_excl_slow_start_mbps", s.u3GoodputExclSlowStartMbps)
            put("u3_window_target_ms", s.u3WindowTargetMs)
            put("u3_window_actual_ms", s.u3WindowActualMs)
            put("u3_bytes_transferred", s.u3BytesTransferred)
            put("u3_rtt_ref_ms_pre", s.u3RttRefMsPre)
            put("u3_rtt_ref_ms_post", s.u3RttRefMsPost)
            put("u3_rtt_drift_ratio", s.u3RttDriftRatio)
            put("u3_rtt_dominance_ratio", s.u3RttDominanceRatio)
            put("u3_rtt_dominance_ok", s.u3RttDominanceOk)
            // T75/D-534 §2：spec §8.3.3 的「窗口提前完成」情形本身上 wire。此前它只折进
            // low_confidence 并打一条 ADAPTIVE_*_WINDOW 日志——而 §8.3.3 的目的句是
            // 「不得与正常的窗口到点截断样本混算」，混算发生在分析层，分析层看不到日志。
            put("u3_window_underrun", s.u3WindowUnderrun)
            put("d3_goodput_mbps", s.d3GoodputMbps); put("d3_grade", s.d3Grade)
            put("d3_goodput_excl_slow_start_mbps", s.d3GoodputExclSlowStartMbps)
            put("d3_window_target_ms", s.d3WindowTargetMs)
            put("d3_window_actual_ms", s.d3WindowActualMs)
            put("d3_bytes_transferred", s.d3BytesTransferred)
            put("d3_rtt_ref_ms_pre", s.d3RttRefMsPre)
            put("d3_rtt_ref_ms_post", s.d3RttRefMsPost)
            put("d3_rtt_drift_ratio", s.d3RttDriftRatio)
            put("d3_rtt_dominance_ratio", s.d3RttDominanceRatio)
            put("d3_rtt_dominance_ok", s.d3RttDominanceOk)
            put("d3_window_underrun", s.d3WindowUnderrun)
            put("seq_gap_count", s.seqGapCount)
            put("seq_dup_count", s.seqDupCount)
        })
        put("clock", buildJsonObject {
            put("offset_start_us", s.offsetStartUs)
            put("offset_end_us", s.offsetEndUs)
            put("drift_ppm", s.offsetDriftPpm)
            put("offset_suspect", s.offsetSuspect)
            // T64 §8.3/D-506：非必填（历史语料没有它，进 required 会让既有 63 份 JSONL
            // 全部违约，spec/README §3 只增不改不删）。测不出为 null（旧服务端不回带
            // anchor），不以 0 顶替——0 恰是「钟完全对齐」的合法值，混淆两者最危险。
            put("wall_skew_ms", s.wallSkewMs)
        })
        put("network_snapshot", buildJsonObject {
            put("transport", s.netTransport)
            put("capabilities", s.netCapabilities)
            put("interface", s.netInterfaceName)
            put("server_observed_addr", s.serverObservedAddr)
            // radio_ctx（RADIO_CONTEXT_WIRING_SPEC v1.0，D-367）：radioStale 非 null
            // = 导出运行过（蜂窝场景恒有，含零样本壳）；wifi 场景与 v16 之前的历史行
            // radioStale==null → 不写该键（规格 §2：不写全 null 壳）。不可得项写 null，
            // 禁哨兵（R-10）。
            val stale = s.radioStale
            if (stale != null) {
                put("radio", buildJsonObject {
                    put("rat", s.radioRat)
                    put("rsrp_dbm", s.radioRsrpDbm)
                    put("sinr_db", s.radioSinrDb)
                    put("pci", s.radioPci)
                    put("tac", s.radioTac)
                    put("arfcn", s.radioArfcn)
                    put("sampled_n", s.radioSampledN)
                    put("stale", stale)
                })
            }
        })
        put("parse", buildJsonObject {
            put("parse_dur_us", s.parseDurUsTotal)
            put("per_event_parse_us", s.perEventParseUs)
        })
        // per-KPI 质量（D-373，试点报告附二第一建议）：低置信判词此前只有结论没有理由
        // ——哪个 KPI 差几个样本设备知道、契约不说，标记恒真且无从定位。kpiSampleCounts
        // 非 null = 导出运行过（v17+）；历史行不写该键，不编造。词汇与 lowConfidenceKpis
        // 同源（TestEngine.kpiValuePairs 单一清单）。
        val sampleCounts = s.kpiSampleCounts
        if (sampleCounts != null) {
            val lowSet = s.lowConfidenceKpis.split(",").filter { it.isNotBlank() }.toSet()
            put("kpi_quality", buildJsonObject {
                sampleCounts.split(",").filter { it.isNotBlank() }.forEach { pair ->
                    val name = pair.substringBefore(":")
                    val n = pair.substringAfter(":").toIntOrNull()
                    put(name, buildJsonObject {
                        put("sample_count", n)
                        put("low_confidence", name in lowSet)
                    })
                }
            })
        }
        // P1-C08 遗留接线：批化标注（additive 扩展——server/handlers_results.go 的
        // validateResultContract 只校验必填字段、不拒新增字段，已读码确认）。
        // R-05：score/attribution 仅为标注与取证证据，服务端/下游不得据此改判 validity。
        put("buffering", buildJsonObject {
            put("score", s.bufferingScore)
            put("attribution", s.bufferingAttribution)
            put("sample_count", s.bufferingSampleCount)
            put("sawtooth_ratio", s.bufferingSawtoothRatio)
            put("near_zero_arrival_ratio", s.bufferingNearZeroRatio)
            put("lag1_autocorrelation", s.bufferingLag1Autocorr)
            put("batch_count", s.bufferingBatchCount)
            put("best_grid_us", s.bufferingBestGridUs)
            put("jank_overlap_ratio", s.bufferingJankOverlapRatio)
        })
        // ITL 对数分桶直方图（R-27 合同：桶界 = 对数网格 ∪ T2/T3/T4 门限锚点）
        put("itl_histogram", buildJsonObject {
            put("buckets_version", ItlHistogram.BUCKETS_VERSION)
            putJsonArray("edges_ms") { hist.edgesMs.forEach { add(it) } }
            putJsonArray("counts") { hist.counts.forEach { add(it) } }
            put("total", hist.total)
        })
    }
}
