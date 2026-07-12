package com.aneb.probe.data

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(
    entities = [TestRun::class, TokenEventEntity::class],
    version = 1,
    exportSchema = false, // TODO(阶段1): 开 schema 导出并纳入版本管理
)
abstract class AnebDatabase : RoomDatabase() {
    abstract fun testRunDao(): TestRunDao
    abstract fun tokenEventDao(): TokenEventDao

    companion object {
        @Volatile
        private var instance: AnebDatabase? = null

        fun get(context: Context): AnebDatabase =
            instance ?: synchronized(this) {
                instance ?: Room.databaseBuilder(
                    context.applicationContext,
                    AnebDatabase::class.java,
                    "aneb-probe.db",
                ).build().also { instance = it }
            }
    }
}
