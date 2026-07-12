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
    ],
    // v3：P1-C05/C06 接线——TestRun 扩 run 级字段；新增 scenario_result / echo_sample；
    // token_event 增 scenarioKey/streamIndex 维度
    // v4：P1-C07——scenario_result 增 lowConfidenceKpis；新增 report_body（导出 JSON 源）
    // v5：阶段 2 C 组——新增 continuity_result（连续性实验汇总，additive）
    // v6：阶段 2 合并——新增 api_probe_result（真实 API 探针，claim scope 独立不进 AQS）
    // v7：P2-C05——新增 ab_result（Cronet TCP vs QUIC(h3) A/B 逐样本，stack=cronet，additive）
    version = 7,
    exportSchema = false, // TODO(阶段1 后续): 开 schema 导出并纳入版本管理
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

        fun get(context: Context): AnebDatabase =
            instance ?: synchronized(this) {
                instance ?: Room.databaseBuilder(
                    context.applicationContext,
                    AnebDatabase::class.java,
                    "aneb-probe.db",
                )
                    // v6 起 schema 变更必须写显式 Migration（历史数据是取证资产，
                    // 不可静默丢弃）——v6→v7 见上方 MIGRATION_6_7（additive）。
                    .addMigrations(MIGRATION_6_7)
                    // 兜底仅覆盖 <6 的开发期版本（无显式迁移路径时毁库重建）。
                    .fallbackToDestructiveMigration()
                    .build()
                    .also { instance = it }
            }
    }
}
