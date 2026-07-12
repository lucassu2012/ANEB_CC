package com.aneb.probe.data

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(
    entities = [
        TestRun::class,
        TokenEventEntity::class,
        ScenarioResultEntity::class,
        EchoSampleEntity::class,
        EnvEventEntity::class,
        RadioSampleEntity::class,
        ReportBodyEntity::class,
    ],
    // v3：P1-C05/C06 接线——TestRun 扩 run 级字段；新增 scenario_result / echo_sample；
    // token_event 增 scenarioKey/streamIndex 维度
    // v4：P1-C07——scenario_result 增 lowConfidenceKpis；新增 report_body（导出 JSON 源）
    version = 4,
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

    companion object {
        @Volatile
        private var instance: AnebDatabase? = null

        fun get(context: Context): AnebDatabase =
            instance ?: synchronized(this) {
                instance ?: Room.databaseBuilder(
                    context.applicationContext,
                    AnebDatabase::class.java,
                    "aneb-probe.db",
                )
                    // 开发期口径：schema 变更直接毁库重建，不写迁移。
                    // 发布取证版前必须换成显式 Migration（历史数据是取证资产，不可静默丢弃）。
                    .fallbackToDestructiveMigration()
                    .build()
                    .also { instance = it }
            }
    }
}
