package com.aneb.probe.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * DB v21 迁移 SQL 存在性单测（T75 / D-534 §2：`window_underrun` 进契约，
 * `scenario_result` 加 2 列）。取舍同 [MigrationV20Test]：JVM 层锚定迁移合同——
 * 版本号 20→21、additive-only、新列可空无默认（R-10：缺失 ≠ false）。
 *
 * 这两列存在的理由，写在这里以免日后被当成冗余删掉：
 * `lowConf = !rttDominanceOk || windowUnderrun`，故 `rttDominanceOk=false` 时
 * `low_confidence` 恒真、underrun 被完全掩盖——**它不能从既有字段反推**。
 */
class MigrationV21Test {

    /**
     * 从模块工作目录（`app/probe`）向上找仓库根相对路径。
     *
     * 逐字照 `RttDominanceGuardTest` / `VoiceExecutionPlanParityTest` / `AdapterSpecTest`
     * 的既有惯例——**不要手算层数**：`user.dir` 是模块目录不是 `app/`，本测试初版按
     * `parentFile` 算就拼出了 `app/app/probe/...` 并当场变红。
     */
    private fun repoFile(relFromRepoRoot: String): File {
        var cur: File? = File(System.getProperty("user.dir") ?: ".").absoluteFile
        while (cur != null) {
            val cand = File(cur, relFromRepoRoot)
            if (cand.isFile) return cand
            cur = cur.parentFile
        }
        error("找不到 $relFromRepoRoot（从 user.dir 向上未命中）")
    }

    @Test
    fun migrationVersionsAre20To21() {
        assertEquals(20, AnebDatabase.MIGRATION_20_21.startVersion)
        assertEquals(21, AnebDatabase.MIGRATION_20_21.endVersion)
    }

    @Test
    fun addsExactlyTwoColumnsAdditively() {
        assertEquals(2, AnebDatabase.MIGRATION_20_21_SQL.size)
        val expected = mapOf(
            "u3WindowUnderrun" to "INTEGER",
            "d3WindowUnderrun" to "INTEGER",
        )
        val seenCols = HashSet<String>()
        AnebDatabase.MIGRATION_20_21_SQL.forEach { sql ->
            assertTrue(
                "非 scenario_result 加列语句: $sql",
                sql.startsWith("ALTER TABLE `scenario_result` ADD COLUMN `"),
            )
            val col = Regex("ADD COLUMN `([^`]+)`").find(sql)?.groupValues?.get(1)
            assertTrue("从 SQL 取不到列名: $sql", col != null)
            seenCols.add(col!!)
            val affinity = expected[col]
            assertTrue("未预期的新列名 `$col`: $sql", affinity != null)
            val upper = sql.uppercase()
            assertTrue("列 `$col` 须 $affinity affinity: $sql", upper.endsWith(" $affinity"))
            assertTrue(
                "破坏性语句: $sql",
                !upper.contains("DROP TABLE") && !upper.contains("DROP COLUMN") &&
                    !upper.contains("DELETE FROM"),
            )
            assertTrue("新列不得 NOT NULL（R-10 可空）", !upper.contains("NOT NULL"))
            assertTrue("新列不得带默认值（R-10：缺失 ≠ false）", !upper.contains("DEFAULT"))
        }
        assertEquals("2 列一个不多一个不少全覆盖", expected.keys, seenCols)
    }

    /**
     * 迁移列名必须与实体字段名逐字一致——Room 按 @Entity 期望 schema 逐列校验，
     * 对不上是**真机启动时**才 fail-fast。同 [MigrationV20Test] 纪律。
     */
    @Test
    fun migrationColumnNamesMatchTheEntityFieldNames() {
        val fields = ScenarioResultEntity::class.java.declaredFields.map { it.name }.toSet()
        AnebDatabase.MIGRATION_20_21_SQL.forEach { sql ->
            val col = Regex("ADD COLUMN `([^`]+)`").find(sql)?.groupValues?.get(1)
            assertTrue("从 SQL 取不到列名: $sql", col != null)
            assertTrue(
                "迁移列 `$col` 在 ScenarioResultEntity 里没有同名字段——Room 会在真机启动时炸",
                fields.contains(col),
            )
        }
    }

    /**
     * **[MigrationV20Test] 没有的一条**：新列必须真的落进了 Room 导出的 schema 快照。
     *
     * 迁移 SQL 与实体字段对上，只证明「我打算加这两列」；Room 真正拿来比对的是
     * `app/probe/schemas/<db>/21.json`。快照没生成或没含新列时，前三条测试照样全绿，
     * 而**真机升级时 Room 才抛 IllegalStateException**——那是最晚、最贵的发现时机。
     */
    @Test
    fun theExportedSchemaSnapshotActuallyCarriesTheNewColumns() {
        val snapshot = repoFile("app/probe/schemas/com.aneb.probe.data.AnebDatabase/21.json")
        val text = snapshot.readText()
        assertTrue("快照里 version 不是 21", Regex("\"version\"\\s*:\\s*21").containsMatchIn(text))
        AnebDatabase.MIGRATION_20_21_SQL.forEach { sql ->
            val col = Regex("ADD COLUMN `([^`]+)`").find(sql)!!.groupValues[1]
            assertTrue(
                "迁移加了列 `$col`，但 v21 schema 快照里没有它——真机升级时 Room 才会炸",
                text.contains("\"columnName\": \"$col\""),
            )
        }
    }
}
