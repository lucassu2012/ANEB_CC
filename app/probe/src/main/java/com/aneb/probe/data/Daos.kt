package com.aneb.probe.data

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.Query

@Dao
interface TestRunDao {
    @Insert
    suspend fun insert(run: TestRun)

    @Query("SELECT * FROM test_run ORDER BY startedAtEpochMs DESC")
    suspend fun all(): List<TestRun>
}

@Dao
interface TokenEventDao {
    /** 阶段 1 起：phase 结束后一次性批量事务写入（读循环内禁逐条写，R-16/§4.10）。 */
    @Insert
    suspend fun insertAll(events: List<TokenEventEntity>)

    @Query("SELECT * FROM token_event WHERE runId = :runId ORDER BY seq")
    suspend fun forRun(runId: String): List<TokenEventEntity>

    @Query("SELECT COUNT(*) FROM token_event WHERE runId = :runId")
    suspend fun countForRun(runId: String): Long
}
