package com.aneb.probe.data

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

@Database(
    entities = [
        TestRun::class,
        TokenEventEntity::class,
        ScenarioResultEntity::class,
        EchoSampleEntity::class,
        EnvEventEntity::class,
        RadioSampleEntity::class,
        ReportBodyEntity::class,
        ContinuityResultEntity::class,
        ApiProbeResultEntity::class,
        AbResultEntity::class,
        VoiceResultEntity::class,
        SyntheticResultEntity::class,
        AdapterObsEntity::class,
    ],
    // v3：P1-C05/C06 接线——TestRun 扩 run 级字段；新增 scenario_result / echo_sample；
    // token_event 增 scenarioKey/streamIndex 维度
    // v4：P1-C07——scenario_result 增 lowConfidenceKpis；新增 report_body（导出 JSON 源）
    // v5：阶段 2 C 组——新增 continuity_result（连续性实验汇总，additive）
    // v6：阶段 2 合并——新增 api_probe_result（真实 API 探针，claim scope 独立不进 AQS）
    // v7：P2-C05——新增 ab_result（Cronet TCP vs QUIC(h3) A/B 逐样本，stack=cronet，additive）
    // v8：阶段3 遗留接线——scenario_result 增 buffering* 标注列（P1-C08，R-05 不改 validity）；
    //     test_run 增 aqsV02* 并列出分列（阶段2 C03，无 C 数据时全 null=v0.1 语义不变）
    // v9：阶段3 GPS 路测——radio_sample 增 lat/lon/accuracyM 可空列（坐标只入本地，
    //     绝不进上报体；§9.1 隐私边界，路测开关默认关）
    // v10：阶段3 SNI 双通道——test_run 增 sniReachable/sniReachMs/ipReachable/ipReachMs
    //      可空列（run 前连接可达性探测：带 SNI vs bare-IP 的 TLS 握手结果+耗时，additive）
    // v11：阶段3 真机跨网迁移修复——continuity_result 增 c2CrossNetworkRecoveries 可空列
    //      （真机硬切换拆除原绑定网后迁到新默认网恢复的样本数，两种 C2 语义，D-23，additive）
    // v12：D-42 语音结果落库——新增 voice_result（语音模式 Done 样本实测值，v1/v2 双口径
    //      共表以 caliber 区分；观测口径独立于 token AQS 各表，additive）
    // v13：合成子测结果落库——新增 synthetic_result（恢复子测 D-40 / 弱网整形对照 D-43 的
    //      Done 样本实测值共表，kind 区分；合成口径独立结论恒 LOW/INCONCLUSIVE，additive）
    // v14：Profile 3 观察数据落库——新增 adapter_obs（无障碍观察会话快照，只落规格匹配会话；
    //      观察=端到端体验代理≠网络口径，独立于 AQS 各表，恒 LOW/INCONCLUSIVE，additive）
    // v15：adapter_obs 加 sessionSpanMs 列（spine-3 C6 会话时长 ui-proxy，additive ADD COLUMN）
    // v16：scenario_result 增 radio* 八列（RADIO_CONTEXT_WIRING_SPEC v1.0 接线，D-367：
    //      场景级无线导出进上报体 network_snapshot.radio;全部可空,历史行 NULL,additive）
    // v17：scenario_result 增 kpiSampleCounts 列（D-373:per-KPI 有效样本数进上报体
    //      kpi_quality;低置信判词从此带理由;可空,历史行 NULL,additive ADD COLUMN）
    // v18：voice_result 增 m7MaxFrameGapMs / voiceNearZeroArrivalRatio 两列（D-390 §5 B′：
    //      M7「最长帧间静默」用 max 而非分位数——P95 会把罕见但致命的长冻结丢掉;
    //      先落库不等计分实施,理由=chunk_us 被点名 20 处却从未落盘、M3 至今无法复核;
    //      可空,历史行 NULL＝「跑在 M7 之前」而非「为零」,additive ADD COLUMN）
    // v19：scenario_result 增 d1GoodputMbps / d1Grade 两列（T47 批①,D-468/D-469：D1 半成品
    //      补齐——KpiCalculator 早算出 d1GoodputMbps 却从未落库上线；门限复用既有
    //      AqsScorer.D1_ANCHORS/basic_network D1 QualityTarget 取值 25/8/2,非新造;
    //      可空,历史行 NULL＝「跑在 D1 上线之前」而非「为零」,additive ADD COLUMN）
    // v20：scenario_result 增 22 列（T47 批③,D-468/D-469：单流自适应窗口 goodput 探针
    //      U3/D3——goodput/excl_slow_start/grade(恒null)/window_target_ms/window_actual_ms/
    //      bytes_transferred/rtt_ref_ms_pre/_post/rtt_drift_ratio/rtt_dominance_ratio/
    //      rtt_dominance_ok 各 11 列×2 方向;诊断期不进任何 AQS facet;可空,历史行/非
    //      s4_throughput 场景 NULL＝「未跑该探针」而非「为零」,additive ADD COLUMN）
    version = 20,
    exportSchema = true, // T45/D-463 §6.2：打开，快照进 app/probe/schemas/（ksp room.schemaLocation）
)
abstract class AnebDatabase : RoomDatabase() {
    abstract fun testRunDao(): TestRunDao
    abstract fun tokenEventDao(): TokenEventDao
    abstract fun scenarioResultDao(): ScenarioResultDao
    abstract fun echoSampleDao(): EchoSampleDao
    abstract fun envEventDao(): EnvEventDao
    abstract fun radioSampleDao(): RadioSampleDao
    abstract fun reportBodyDao(): ReportBodyDao
    abstract fun continuityResultDao(): ContinuityResultDao
    abstract fun apiProbeResultDao(): ApiProbeResultDao
    abstract fun abResultDao(): AbResultDao
    abstract fun voiceResultDao(): VoiceResultDao
    abstract fun syntheticResultDao(): SyntheticResultDao
    abstract fun adapterObsDao(): AdapterObsDao

    companion object {
        @Volatile
        private var instance: AnebDatabase? = null

        /**
         * v6 → v7（P2-C05，additive）：新增 ab_result 表 + runId 索引，不触碰既有表——
         * 已落库的历史取证数据（v6 含 api_probe_result 及之前全部表）原样保留。
         *
         * SQL 与 KSP 生成的 AnebDatabase_Impl.createAllTables 严格一致（列序/affinity/
         * NOT NULL/AUTOINCREMENT/索引名 index_ab_result_runId）：Room 迁移后会按 @Entity
         * 期望 schema 逐列校验，任何偏差 fail-fast 抛 IllegalStateException，不会静默错表。
         *
         * 验证：room-testing 的 MigrationTestHelper 需要 instrumentation（androidTest），
         * JVM 单测覆盖不到；本项目不为此引入 androidTest 基建。人工验证步骤：
         *  1. 安装 db v6 的旧版 APK 并跑一次场景（产生历史 run 数据）；
         *  2. 覆盖安装本版本，启动 app：既有 run/结果仍可见（未被毁库重建）；
         *  3. adb shell "run-as com.aneb.probe sqlite3 databases/aneb-probe.db '.schema ab_result'"
         *     输出与本迁移 CREATE 语句一致；
         *  4. 跑一次 A/B（AB_DB_WRITE 落库成功），logcat 无
         *     "Migration didn't properly handle" 异常。
         */
        internal val MIGRATION_6_7 = object : Migration(6, 7) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    "CREATE TABLE IF NOT EXISTS `ab_result` (" +
                        "`id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, " +
                        "`runId` TEXT NOT NULL, " +
                        "`startedAtEpochMs` INTEGER NOT NULL, " +
                        "`serverBase` TEXT NOT NULL, " +
                        "`stack` TEXT NOT NULL, " +
                        "`claimScope` TEXT NOT NULL, " +
                        "`profileId` TEXT NOT NULL, " +
                        "`phaseIndex` INTEGER NOT NULL, " +
                        "`sampleIndex` INTEGER NOT NULL, " +
                        "`groupLabel` TEXT NOT NULL, " +
                        "`bin` TEXT NOT NULL, " +
                        "`negotiatedProtocol` TEXT, " +
                        "`httpCode` INTEGER, " +
                        "`error` TEXT, " +
                        "`ttftMs` REAL, " +
                        "`itlP50Ms` REAL, " +
                        "`itlP95Ms` REAL, " +
                        "`itlSampleCount` INTEGER NOT NULL, " +
                        "`stallCount` INTEGER, " +
                        "`stallRate` REAL, " +
                        "`gapCount` INTEGER NOT NULL, " +
                        "`dupCount` INTEGER NOT NULL, " +
                        "`tokenEventCount` INTEGER NOT NULL, " +
                        "`truncatedEarly` INTEGER NOT NULL)"
                )
                db.execSQL(
                    "CREATE INDEX IF NOT EXISTS `index_ab_result_runId` ON `ab_result` (`runId`)"
                )
            }
        }

        /**
         * v7 → v8 的全部语句（阶段3 遗留接线，additive；JVM 单测锚定存在性与 additive-only）：
         *  - scenario_result 增 9 个 buffering* 标注列（P1-C08；R-05 分数只作标注不改 validity）；
         *  - test_run 增 8 个 aqsV02* 并列出分列（阶段2 C03）。
         * 全部为**可空列、无默认值**（新列 Kotlin 侧默认 null）：ALTER TABLE ADD COLUMN 后
         * Room 按 @Entity 期望 schema 逐列校验（列名/affinity/notNull），偏差 fail-fast——
         * 做法与 [MIGRATION_6_7] 一致（列名=字段名，affinity：Double→REAL、
         * Int/Long/Boolean→INTEGER、String→TEXT，与 KSP 生成的期望 schema 一致）。
         * 历史行新列值为 NULL＝"当时未检测/无 v0.2 分支"，与 R-10 null 语义一致。
         */
        internal val MIGRATION_7_8_SQL: List<String> = listOf(
            "ALTER TABLE `scenario_result` ADD COLUMN `bufferingScore` REAL",
            "ALTER TABLE `scenario_result` ADD COLUMN `bufferingAttribution` TEXT",
            "ALTER TABLE `scenario_result` ADD COLUMN `bufferingSampleCount` INTEGER",
            "ALTER TABLE `scenario_result` ADD COLUMN `bufferingSawtoothRatio` REAL",
            "ALTER TABLE `scenario_result` ADD COLUMN `bufferingNearZeroRatio` REAL",
            "ALTER TABLE `scenario_result` ADD COLUMN `bufferingLag1Autocorr` REAL",
            "ALTER TABLE `scenario_result` ADD COLUMN `bufferingBatchCount` INTEGER",
            "ALTER TABLE `scenario_result` ADD COLUMN `bufferingBestGridUs` INTEGER",
            "ALTER TABLE `scenario_result` ADD COLUMN `bufferingJankOverlapRatio` REAL",
            "ALTER TABLE `test_run` ADD COLUMN `aqsV02Score` REAL",
            "ALTER TABLE `test_run` ADD COLUMN `aqsV02LowConfidence` INTEGER",
            "ALTER TABLE `test_run` ADD COLUMN `aqsV02VetoApplied` INTEGER",
            "ALTER TABLE `test_run` ADD COLUMN `aqsV02NotComputableReason` TEXT",
            "ALTER TABLE `test_run` ADD COLUMN `aqsV02ContinuityRunId` TEXT",
            "ALTER TABLE `test_run` ADD COLUMN `aqsV02ContinuityStartedAtEpochMs` INTEGER",
            "ALTER TABLE `test_run` ADD COLUMN `aqsV02C1DropRate` REAL",
            "ALTER TABLE `test_run` ADD COLUMN `aqsV02C2RecoveryMs` REAL",
        )

        /**
         * v7 → v8（阶段3 遗留接线，additive）：只加列不动数据——已落库的历史取证数据
         * （v7 含 ab_result 及之前全部表）原样保留。人工验证步骤同 [MIGRATION_6_7] KDoc
         * （覆盖安装后既有 run 可见、.schema 输出含新列、logcat 无 Migration 异常）。
         */
        internal val MIGRATION_7_8 = object : Migration(7, 8) {
            override fun migrate(db: SupportSQLiteDatabase) {
                MIGRATION_7_8_SQL.forEach(db::execSQL)
            }
        }

        /**
         * v8 → v9 的全部语句（阶段3 GPS 路测，additive；JVM 单测锚定存在性与 additive-only）：
         * radio_sample 增 lat / lon / accuracyM 三个**可空、无默认值**坐标列（Double→REAL，
         * 与 KSP 期望 schema 一致，做法同 [MIGRATION_7_8]）。历史行新列值为 NULL＝
         * "当时未开路测/无 fix"，与 R-10 null 语义一致。隐私边界（设计文档 §9.1）：
         * 坐标只入本地 Room 与本地轨迹导出，绝不进 /results 上报体。
         */
        internal val MIGRATION_8_9_SQL: List<String> = listOf(
            "ALTER TABLE `radio_sample` ADD COLUMN `lat` REAL",
            "ALTER TABLE `radio_sample` ADD COLUMN `lon` REAL",
            "ALTER TABLE `radio_sample` ADD COLUMN `accuracyM` REAL",
        )

        /**
         * v8 → v9（阶段3 GPS 路测，additive）：只加列不动数据。人工验证步骤同
         * [MIGRATION_6_7] KDoc（覆盖安装后既有 run 可见、.schema 输出含新列、
         * logcat 无 Migration 异常）。
         */
        internal val MIGRATION_8_9 = object : Migration(8, 9) {
            override fun migrate(db: SupportSQLiteDatabase) {
                MIGRATION_8_9_SQL.forEach(db::execSQL)
            }
        }

        /**
         * v9 → v10 的全部语句（阶段3 SNI 双通道，additive；JVM 单测锚定存在性与 additive-only）：
         * test_run 增 4 个连接可达性列——sniReachable/ipReachable（TEXT，TLS 握手结果
         * ok/rst/timeout/error:*）与 sniReachMs/ipReachMs（INTEGER，探测耗时 ms）。全部
         * **可空、无默认值**（新列 Kotlin 侧默认 null），做法同 [MIGRATION_8_9]。历史行
         * 与未探测（如 WiFi 路径）新列值 NULL＝"当时未探测"，与 R-10 null 语义一致。
         */
        internal val MIGRATION_9_10_SQL: List<String> = listOf(
            "ALTER TABLE `test_run` ADD COLUMN `sniReachable` TEXT",
            "ALTER TABLE `test_run` ADD COLUMN `sniReachMs` INTEGER",
            "ALTER TABLE `test_run` ADD COLUMN `ipReachable` TEXT",
            "ALTER TABLE `test_run` ADD COLUMN `ipReachMs` INTEGER",
        )

        /**
         * v9 → v10（阶段3 SNI 双通道，additive）：只加列不动数据。人工验证步骤同
         * [MIGRATION_6_7] KDoc（覆盖安装后既有 run 可见、.schema 输出含新列、
         * logcat 无 Migration 异常）。
         */
        internal val MIGRATION_9_10 = object : Migration(9, 10) {
            override fun migrate(db: SupportSQLiteDatabase) {
                MIGRATION_9_10_SQL.forEach(db::execSQL)
            }
        }

        /**
         * v10 → v11 的全部语句（阶段3 真机跨网迁移修复，additive；JVM 单测锚定存在性与
         * additive-only）：continuity_result 增 1 个**可空、无默认值**列
         * c2CrossNetworkRecoveries（Int?→INTEGER，与 KSP 期望 schema 一致，做法同
         * [MIGRATION_9_10]）。历史行（v10 及之前，含模拟器 508ms 基线 run）新列值为 NULL＝
         * "当时未区分 same/cross 语义"，与 R-10 null 语义一致；真机硬切换恢复的 run 记实际
         * 跨网迁移样本数（D-23，两种 C2 语义见 KPI 文档 §5.1）。
         */
        internal val MIGRATION_10_11_SQL: List<String> = listOf(
            "ALTER TABLE `continuity_result` ADD COLUMN `c2CrossNetworkRecoveries` INTEGER",
        )

        /**
         * v10 → v11（阶段3 真机跨网迁移修复，additive）：只加列不动数据——已落库的历史取证
         * 数据（v10 含 continuity_result 及之前全部表）原样保留。人工验证步骤同 [MIGRATION_6_7]
         * KDoc（覆盖安装后既有 run 可见、.schema continuity_result 输出含新列、logcat 无
         * Migration 异常）。
         */
        internal val MIGRATION_10_11 = object : Migration(10, 11) {
            override fun migrate(db: SupportSQLiteDatabase) {
                MIGRATION_10_11_SQL.forEach(db::execSQL)
            }
        }

        /**
         * v11 → v12 的全部语句（D-42 语音结果落库，additive；JVM 单测锚定存在性与
         * additive-only）：新增 voice_result 表（无索引），不触碰既有表。SQL 与 KSP 生成的
         * AnebDatabase_Impl.createAllTables 严格一致（列序=字段声明序，affinity：
         * Double→REAL、Int/Long/Boolean→INTEGER、String→TEXT），做法同 [MIGRATION_6_7]——
         * Room 迁移后按 @Entity 期望 schema 逐列校验，偏差 fail-fast，不会静默错表。
         * 指标列全部**可空、无默认值**（R-10：Sample 的 null 原样落库，禁 0/哨兵值）。
         */
        internal val MIGRATION_11_12_SQL: List<String> = listOf(
            "CREATE TABLE IF NOT EXISTS `voice_result` (" +
                "`id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, " +
                "`tsEpochMs` INTEGER NOT NULL, " +
                "`caliber` TEXT, " +
                "`lowConfidence` INTEGER NOT NULL, " +
                "`rttMs` REAL, " +
                "`jitterMs` REAL, " +
                "`upFrameJitterMs` REAL, " +
                "`downFrameJitterMs` REAL, " +
                "`mouthEarBudgetMs` REAL, " +
                "`framesSent` INTEGER, " +
                "`framesRecv` INTEGER, " +
                "`ttfbP50Ms` REAL, " +
                "`ttfbP95Ms` REAL, " +
                "`downNetJitterMs` REAL, " +
                "`mouthEarProxyMs` REAL, " +
                "`turnSwitchP50Ms` REAL, " +
                "`bargeStopMaxMs` REAL, " +
                "`turnsOk` INTEGER)",
        )

        /**
         * v11 → v12（D-42 语音结果落库，additive）：只建新表不动数据——已落库的历史取证
         * 数据（v11 含 continuity_result 新列及之前全部表）原样保留。人工验证步骤同
         * [MIGRATION_6_7] KDoc（覆盖安装后既有 run 可见、.schema voice_result 输出与本
         * CREATE 语句一致、跑一次语音测量 VOICE_SAVED 落库成功、logcat 无 Migration 异常）。
         */
        internal val MIGRATION_11_12 = object : Migration(11, 12) {
            override fun migrate(db: SupportSQLiteDatabase) {
                MIGRATION_11_12_SQL.forEach(db::execSQL)
            }
        }

        /**
         * v12 → v13 的全部语句（合成子测结果落库，additive；JVM 单测锚定存在性与
         * additive-only）：新增 synthetic_result 表（无索引），不触碰既有表。SQL 与 KSP
         * 生成的 AnebDatabase_Impl.createAllTables 严格一致（列序=字段声明序，affinity：
         * Double→REAL、Int/Long/Boolean→INTEGER、String→TEXT），做法同 [MIGRATION_11_12]——
         * Room 迁移后按 @Entity 期望 schema 逐列校验，偏差 fail-fast，不会静默错表。
         * 指标列全部**可空、无默认值**（R-10：Sample 的 null 原样落库，禁 0/哨兵值）；
         * recovery / shaped 两类共表以 kind 区分，各自不用的列置 null。
         */
        internal val MIGRATION_12_13_SQL: List<String> = listOf(
            "CREATE TABLE IF NOT EXISTS `synthetic_result` (" +
                "`id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, " +
                "`tsEpochMs` INTEGER NOT NULL, " +
                "`kind` TEXT NOT NULL, " +
                "`confidence` TEXT NOT NULL, " +
                "`recoveryMs` REAL, " +
                "`outage503` INTEGER, " +
                "`postSuccess` INTEGER, " +
                "`postTotal` INTEGER, " +
                "`rttP95Ms` REAL, " +
                "`meetsTargets` INTEGER, " +
                "`shapedDownMbps` REAL, " +
                "`shapedUpMbps` REAL, " +
                "`shapedRttMs` REAL)",
        )

        /**
         * v12 → v13（合成子测结果落库，additive）：只建新表不动数据——已落库的历史取证
         * 数据（v12 含 voice_result 及之前全部表）原样保留。人工验证步骤同 [MIGRATION_6_7]
         * KDoc（覆盖安装后既有 run 可见、.schema synthetic_result 输出与本 CREATE 语句一致、
         * 跑一次恢复子测/弱网对照 RECOVERY_SAVED / SHAPED_SAVED 落库成功、logcat 无
         * Migration 异常）。
         */
        internal val MIGRATION_12_13 = object : Migration(12, 13) {
            override fun migrate(db: SupportSQLiteDatabase) {
                MIGRATION_12_13_SQL.forEach(db::execSQL)
            }
        }

        /**
         * v13 → v14 的全部语句（Profile 3 观察数据落库，additive；JVM 单测锚定存在性与
         * additive-only）：新增 adapter_obs 表（无索引），不触碰既有表。SQL 与 KSP 生成的
         * AnebDatabase_Impl.createAllTables 严格一致（列序=字段声明序，affinity：
         * Double→REAL、Int/Long/Boolean→INTEGER、String→TEXT），做法同 [MIGRATION_12_13]——
         * Room 迁移后按 @Entity 期望 schema 逐列校验，偏差 fail-fast，不会静默错表。
         * NOT NULL 恰 6 列（id/tsEpochMs/pkg/events/ruleMatchedEvents/confidence）；指标列全部
         * **可空、无默认值**（R-10：Snapshot 的 null 原样落库，禁 0/哨兵值）。只落规格匹配会话
         * （specId!=null），generic 观察不落库（宿主侧过滤，见 AnebAccessibilityService）。
         */
        internal val MIGRATION_13_14_SQL: List<String> = listOf(
            "CREATE TABLE IF NOT EXISTS `adapter_obs` (" +
                "`id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, " +
                "`tsEpochMs` INTEGER NOT NULL, " +
                "`pkg` TEXT NOT NULL, " +
                "`specId` TEXT, " +
                "`appLabel` TEXT, " +
                "`events` INTEGER NOT NULL, " +
                "`ruleMatchedEvents` INTEGER NOT NULL, " +
                "`firstDeltaMs` INTEGER, " +
                "`cadenceP50Ms` REAL, " +
                "`ttftClusterMs` REAL, " +
                "`ttftSendMs` REAL, " +
                "`anchorSource` TEXT, " +
                "`confidence` TEXT NOT NULL)",
        )

        /**
         * v13 → v14（Profile 3 观察数据落库，additive）：只建新表不动数据——已落库的历史取证
         * 数据（v13 含 synthetic_result 及之前全部表）原样保留。人工验证步骤同 [MIGRATION_6_7]
         * KDoc（覆盖安装后既有 run 可见、.schema adapter_obs 输出与本 CREATE 语句一致、
         * 用户手动进入豆包/DeepSeek 观察后切前台包 ADAPTER_OBS_SAVED 落库成功、logcat 无
         * Migration 异常）。
         */
        internal val MIGRATION_13_14 = object : Migration(13, 14) {
            override fun migrate(db: SupportSQLiteDatabase) {
                MIGRATION_13_14_SQL.forEach(db::execSQL)
            }
        }

        /**
         * v14 → v15 的全部语句（spine-3 C6，additive-only）：adapter_obs 加 `sessionSpanMs` 列
         * （前台观察会话跨度 ui-proxy，ms）。ALTER TABLE ADD COLUMN 追加为末列，与 Entities.kt
         * AdapterObsEntity 末尾新字段的 KSP 期望 schema 一致（affinity REAL、可空、**无默认值**——
         * R-10：Snapshot 的 null 原样落库，禁 0/哨兵）。既有 adapter_obs 行 sessionSpanMs 补 NULL，
         * 不触碰其他表/列＝v14 旧数据全存活。
         */
        internal val MIGRATION_14_15_SQL: List<String> = listOf(
            "ALTER TABLE `adapter_obs` ADD COLUMN `sessionSpanMs` REAL",
        )

        /**
         * v14 → v15（session_span 落库，additive）：只加列不动数据。人工验证同 [MIGRATION_13_14]
         * KDoc（覆盖安装后既有 adapter_obs 行可见且 sessionSpanMs=NULL、.schema 输出含新列、
         * 观察会话切前台后 ADAPTER_OBS_SAVED 落库 session_span_ms 有值、logcat 无 Migration 异常）。
         */
        internal val MIGRATION_14_15 = object : Migration(14, 15) {
            override fun migrate(db: SupportSQLiteDatabase) {
                MIGRATION_14_15_SQL.forEach(db::execSQL)
            }
        }

        /**
         * v15 → v16 的全部语句（radio_ctx 接线，additive-only，D-367）：scenario_result 加
         * radio* 八列（场景级无线导出，RADIO_CONTEXT_WIRING_SPEC §3）。ALTER TABLE ADD COLUMN
         * 逐列追加为末列，与 Entities.kt ScenarioResultEntity 末尾新字段的 KSP 期望 schema
         * 一致（affinity：String→TEXT、Double→REAL、Int/Boolean→INTEGER；全部**可空、
         * 无默认值**——R-10：不可得 null 原样落库，禁 0/哨兵）。既有行八列补 NULL
         * （radioStale=NULL 即「导出未运行」，ResultReporter 据此不为历史行编造 radio 块），
         * 不触碰其他表/列＝v15 旧数据全存活。
         */
        internal val MIGRATION_15_16_SQL: List<String> = listOf(
            "ALTER TABLE `scenario_result` ADD COLUMN `radioRat` TEXT",
            "ALTER TABLE `scenario_result` ADD COLUMN `radioRsrpDbm` REAL",
            "ALTER TABLE `scenario_result` ADD COLUMN `radioSinrDb` REAL",
            "ALTER TABLE `scenario_result` ADD COLUMN `radioPci` INTEGER",
            "ALTER TABLE `scenario_result` ADD COLUMN `radioTac` INTEGER",
            "ALTER TABLE `scenario_result` ADD COLUMN `radioArfcn` INTEGER",
            "ALTER TABLE `scenario_result` ADD COLUMN `radioSampledN` INTEGER",
            "ALTER TABLE `scenario_result` ADD COLUMN `radioStale` INTEGER",
        )

        /**
         * v15 → v16（radio_ctx 落库，additive）：只加列不动数据。人工验证同 [MIGRATION_14_15]
         * KDoc（覆盖安装后既有 scenario_result 行可见且 radio* 全 NULL、.schema 输出含八新列、
         * 跑一次蜂窝场景 SCENARIO_KPI 后新行 radio* 有值、logcat 无 Migration 异常）。
         */
        internal val MIGRATION_15_16 = object : Migration(15, 16) {
            override fun migrate(db: SupportSQLiteDatabase) {
                MIGRATION_15_16_SQL.forEach(db::execSQL)
            }
        }

        /**
         * v16 → v17 的全部语句（per-KPI 样本数落库，additive-only，D-373）：scenario_result 加
         * `kpiSampleCounts` 列（"T1:3,T2:110,…"，与 lowConfidenceKpis 同一短名词汇）。ALTER TABLE
         * ADD COLUMN 追加为末列，与 Entities.kt ScenarioResultEntity 末尾新字段的 KSP 期望 schema
         * 一致（affinity TEXT、可空、**无默认值**——R-10）。既有行补 NULL（=「导出未运行」，
         * ResultReporter 据此不为历史行编造 kpi_quality 块），不触碰其他表/列＝v16 旧数据全存活。
         */
        internal val MIGRATION_16_17_SQL: List<String> = listOf(
            "ALTER TABLE `scenario_result` ADD COLUMN `kpiSampleCounts` TEXT",
        )

        /**
         * v16 → v17（per-KPI 样本数落库，additive）：只加列不动数据。人工验证同 [MIGRATION_15_16]
         * KDoc（覆盖安装后既有行可见且 kpiSampleCounts=NULL、.schema 输出含新列、跑一次场景后
         * 新行有值、logcat 无 Migration 异常）。
         */
        internal val MIGRATION_16_17 = object : Migration(16, 17) {
            override fun migrate(db: SupportSQLiteDatabase) {
                MIGRATION_16_17_SQL.forEach(db::execSQL)
            }
        }

        /**
         * v17 → v18 的全部语句（M7 输入落库，additive-only，D-390 §5 待裁 B′ 经大脑批准）：
         * `voice_result` 加两列——
         * - `m7MaxFrameGapMs`：下行帧到达序列的 `max(相邻帧间隔)`，**max 而非分位数**。
         *   这正是它存在的理由：M2 用 P95，而 P95 会把「罕见但致命」的长冻结丢掉
         *   （实测单次最大偏差 4523.9ms 只占 0.67%，被切在分位点之上，D-390 §5.6）。
         * - `voiceNearZeroArrivalRatio`：`count(帧间隔 ∈ [0,1000µs)) / n`，复用
         *   `BufferingDetector.NEAR_ZERO_ARRIVAL_US`。它答「有没有发生」（批化投递），
         *   **不计分**；严重度由 `m7MaxFrameGapMs` 承担。
         *
         * **为什么先落库、不等 M7 计分实施**：`chunk_us` 的教训——那个字段被源码与规格点名
         * 20 处、自称 M3 的服务端权威，却**从未落盘**，于是 M3 至今无法从任何语料复核
         * （D-390 §4.2）。今天不落盘，明天就没人能复核 M7。
         *
         * ALTER TABLE ADD COLUMN 追加为末列，与 Entities.kt VoiceResultEntity 末尾新字段的
         * KSP 期望 schema 一致（affinity REAL、可空、**无默认值**——R-10）。既有行补 NULL
         * （=「该 run 跑在 M7 落地之前」，**不是**「静默期为零」），不触碰其他表/列＝v17 旧数据全存活。
         */
        internal val MIGRATION_17_18_SQL: List<String> = listOf(
            "ALTER TABLE `voice_result` ADD COLUMN `m7MaxFrameGapMs` REAL",
            "ALTER TABLE `voice_result` ADD COLUMN `voiceNearZeroArrivalRatio` REAL",
        )

        /**
         * v17 → v18（M7 输入落库，additive）：只加列不动数据。人工验证同 [MIGRATION_16_17]
         * KDoc（覆盖安装后既有语音行可见且两列 =NULL、`.schema voice_result` 输出含新列、
         * 跑一次语音后新行有值、logcat 无 Migration 异常）。
         */
        internal val MIGRATION_17_18 = object : Migration(17, 18) {
            override fun migrate(db: SupportSQLiteDatabase) {
                MIGRATION_17_18_SQL.forEach(db::execSQL)
            }
        }

        /**
         * v18 → v19 的全部语句（T47 批①，D-1 半成品补齐，D-468/D-469 大脑批 GO）：
         * `scenario_result` 加两列——
         * - `d1GoodputMbps`：`KpiCalculator.calculate()` 早已算出（PROFILE_FRAMEWORK §2.2
         *   BM-09(b)），但 `ResultReporter`/`kpiValuePairs()` 从未接线，是"契约里要打分、
         *   wire 上从未出现"的半成品（spec §8.1）。本列起把它接入既有落库→上报管线。
         * - `d1Grade`：门限复用既有 `AqsScorer.D1_ANCHORS`/basic_network D1
         *   `QualityTarget`（25/8/2 Mbps），不新造常量（D-312/D-332 同族纪律）。
         *
         * ALTER TABLE ADD COLUMN 追加为末列，与 Entities.kt ScenarioResultEntity 末尾新字段的
         * KSP 期望 schema 一致（affinity REAL/TEXT，均可空，无默认值——R-10）。既有行补 NULL
         * （=「该 run 跑在 D1 上线之前」，**不是**「无下行样本」），不触碰其他表/列＝v18 旧数据全存活。
         */
        internal val MIGRATION_18_19_SQL: List<String> = listOf(
            "ALTER TABLE `scenario_result` ADD COLUMN `d1GoodputMbps` REAL",
            "ALTER TABLE `scenario_result` ADD COLUMN `d1Grade` TEXT",
        )

        /**
         * v18 → v19（D1 半成品补齐，additive）：只加列不动数据。人工验证同 [MIGRATION_16_17]
         * KDoc（覆盖安装后既有 scenario_result 行可见且两列 =NULL、`.schema scenario_result`
         * 输出含新列、跑一次 s3_multimodal 场景后新行 d1GoodputMbps/d1Grade 有值、logcat 无
         * Migration 异常）。
         */
        internal val MIGRATION_18_19 = object : Migration(18, 19) {
            override fun migrate(db: SupportSQLiteDatabase) {
                MIGRATION_18_19_SQL.forEach(db::execSQL)
            }
        }

        /**
         * v19 → v20 的全部语句（T47 批③，单流自适应窗口 goodput 探针 U3/D3，
         * D-468/D-469 大脑批 GO）：`scenario_result` 加 22 列，each direction
         * (u3_/d3_) 11 列：goodput/excl_slow_start/grade(诊断期恒 null)/
         * window_target_ms/window_actual_ms/bytes_transferred/rtt_ref_ms_pre/_post/
         * rtt_drift_ratio/rtt_dominance_ratio/rtt_dominance_ok。
         * ALTER TABLE ADD COLUMN 追加为末列，与 Entities.kt ScenarioResultEntity 末尾新字段的
         * KSP 期望 schema 一致（affinity 见各列，均可空，无默认值——R-10）。既有行补 NULL
         * （=「该场景未跑 s4_throughput」，**不是**「为零」），不触碰其他表/列＝v19 旧数据全存活。
         */
        internal val MIGRATION_19_20_SQL: List<String> = listOf(
            "ALTER TABLE `scenario_result` ADD COLUMN `u3GoodputMbps` REAL",
            "ALTER TABLE `scenario_result` ADD COLUMN `u3Grade` TEXT",
            "ALTER TABLE `scenario_result` ADD COLUMN `u3GoodputExclSlowStartMbps` REAL",
            "ALTER TABLE `scenario_result` ADD COLUMN `u3WindowTargetMs` INTEGER",
            "ALTER TABLE `scenario_result` ADD COLUMN `u3WindowActualMs` REAL",
            "ALTER TABLE `scenario_result` ADD COLUMN `u3BytesTransferred` INTEGER",
            "ALTER TABLE `scenario_result` ADD COLUMN `u3RttRefMsPre` REAL",
            "ALTER TABLE `scenario_result` ADD COLUMN `u3RttRefMsPost` REAL",
            "ALTER TABLE `scenario_result` ADD COLUMN `u3RttDriftRatio` REAL",
            "ALTER TABLE `scenario_result` ADD COLUMN `u3RttDominanceRatio` REAL",
            "ALTER TABLE `scenario_result` ADD COLUMN `u3RttDominanceOk` INTEGER",
            "ALTER TABLE `scenario_result` ADD COLUMN `d3GoodputMbps` REAL",
            "ALTER TABLE `scenario_result` ADD COLUMN `d3Grade` TEXT",
            "ALTER TABLE `scenario_result` ADD COLUMN `d3GoodputExclSlowStartMbps` REAL",
            "ALTER TABLE `scenario_result` ADD COLUMN `d3WindowTargetMs` INTEGER",
            "ALTER TABLE `scenario_result` ADD COLUMN `d3WindowActualMs` REAL",
            "ALTER TABLE `scenario_result` ADD COLUMN `d3BytesTransferred` INTEGER",
            "ALTER TABLE `scenario_result` ADD COLUMN `d3RttRefMsPre` REAL",
            "ALTER TABLE `scenario_result` ADD COLUMN `d3RttRefMsPost` REAL",
            "ALTER TABLE `scenario_result` ADD COLUMN `d3RttDriftRatio` REAL",
            "ALTER TABLE `scenario_result` ADD COLUMN `d3RttDominanceRatio` REAL",
            "ALTER TABLE `scenario_result` ADD COLUMN `d3RttDominanceOk` INTEGER",
        )

        /**
         * v19 → v20（U3/D3 探针，additive）：只加列不动数据。人工验证同 [MIGRATION_18_19]
         * KDoc（覆盖安装后既有 scenario_result 行可见且 22 列 =NULL、`.schema scenario_result`
         * 输出含新列、跑一次 s4_throughput 场景后新行 u3_ 与 d3_ 前缀字段有值、logcat 无 Migration 异常）。
         */
        internal val MIGRATION_19_20 = object : Migration(19, 20) {
            override fun migrate(db: SupportSQLiteDatabase) {
                MIGRATION_19_20_SQL.forEach(db::execSQL)
            }
        }

        fun get(context: Context): AnebDatabase =
            instance ?: synchronized(this) {
                instance ?: Room.databaseBuilder(
                    context.applicationContext,
                    AnebDatabase::class.java,
                    "aneb-probe.db",
                )
                    // v6 起 schema 变更必须写显式 Migration（历史数据是取证资产，
                    // 不可静默丢弃）——v6→v7 / … / v13→v14 见上方（均 additive）。
                    .addMigrations(
                        MIGRATION_6_7, MIGRATION_7_8, MIGRATION_8_9, MIGRATION_9_10, MIGRATION_10_11,
                        MIGRATION_11_12, MIGRATION_12_13, MIGRATION_13_14, MIGRATION_14_15,
                        MIGRATION_15_16, MIGRATION_16_17, MIGRATION_17_18, MIGRATION_18_19,
                        MIGRATION_19_20,
                    )
                    // 兜底仅覆盖 <6 的开发期版本（无显式迁移路径时毁库重建）。
                    .fallbackToDestructiveMigration()
                    .build()
                    .also { instance = it }
            }
    }
}
