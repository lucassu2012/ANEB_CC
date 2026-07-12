package com.aneb.probe.data

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(
    entities = [
        TestRun::class,
        TokenEventEntity::class,
        EnvEventEntity::class,
        RadioSampleEntity::class,
    ],
    version = 2, // v2：新增 env_event / radio_sample 表（R-02/R-12/R-13/R-15/R-16）
    exportSchema = false, // TODO(阶段1 后续): 开 schema 导出并纳入版本管理
)
abstract class AnebDatabase : RoomDatabase() {
    abstract fun testRunDao(): TestRunDao
    abstract fun tokenEventDao(): TokenEventDao
    abstract fun envEventDao(): EnvEventDao
    abstract fun radioSampleDao(): RadioSampleDao

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
