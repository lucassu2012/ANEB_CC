package com.aneb.probe.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * DB v22 迁移 SQL 存在性单测（D-534 §2 并入裁定 / 大脑 08-22 合并版：
 * `skipped_profiles` 进契约，`test_run` 加 1 列）。取舍同 [MigrationV21Test]：
 * JVM 层锚定迁移合同——版本号 21→22、additive-only、新列可空无默认
 * （R-10：缺失 ≠ 空数组——不知道跳没跳，不是知道没跳）。
 *
 * 这一列存在的理由，写在这里以免日后被当成冗余删掉：
 * s4_throughput 缺 profile 时的跳过此前只打一行 PROFILE_WARN 日志，
 * 而**日志到不了分析层**——产物里无从分辨「跑了」和「被跳过」。
 */
class MigrationV22Test {

    /** 从模块工作目录（`app/probe`）向上找仓库根相对路径（同 [MigrationV21Test]）。 */
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
    fun migrationVersionsAre21To22() {
        assertEquals(21, AnebDatabase.MIGRATION_21_22.startVersion)
        assertEquals(22, AnebDatabase.MIGRATION_21_22.endVersion)
    }

    @Test
    fun addsExactlyOneColumnAdditively() {
        assertEquals(1, AnebDatabase.MIGRATION_21_22_SQL.size)
        val sql = AnebDatabase.MIGRATION_21_22_SQL[0]
        assertTrue(
            "非 test_run 加列语句: $sql",
            sql.startsWith("ALTER TABLE `test_run` ADD COLUMN `"),
        )
        val col = Regex("ADD COLUMN `([^`]+)`").find(sql)?.groupValues?.get(1)
        assertEquals("skippedProfiles", col)
        val upper = sql.uppercase()
        assertTrue("列须 TEXT affinity: $sql", upper.endsWith(" TEXT"))
        assertTrue(
            "破坏性语句: $sql",
            !upper.contains("DROP TABLE") && !upper.contains("DROP COLUMN") &&
                !upper.contains("DELETE FROM"),
        )
        assertTrue("新列不得 NOT NULL（R-10 可空）", !upper.contains("NOT NULL"))
        assertTrue("新列不得带默认值（R-10：缺失 ≠ 空数组）", !upper.contains("DEFAULT"))
    }

    /** 迁移列名必须与实体字段名逐字一致（Room 真机启动时才 fail-fast，同 V21 纪律）。 */
    @Test
    fun migrationColumnNameMatchesTheEntityFieldName() {
        val fields = TestRun::class.java.declaredFields.map { it.name }.toSet()
        val col = Regex("ADD COLUMN `([^`]+)`")
            .find(AnebDatabase.MIGRATION_21_22_SQL[0])!!.groupValues[1]
        assertTrue(
            "迁移列 `$col` 在 TestRun 里没有同名字段——Room 会在真机启动时炸",
            fields.contains(col),
        )
    }

    /** 新列必须真的落进 Room 导出的 schema 快照（V21 引入的纪律：快照缺列时
     *  前三条照样全绿，而真机升级时才抛异常——最晚最贵的发现时机）。 */
    @Test
    fun theExportedSchemaSnapshotActuallyCarriesTheNewColumn() {
        val snapshot = repoFile("app/probe/schemas/com.aneb.probe.data.AnebDatabase/22.json")
        val text = snapshot.readText()
        assertTrue("快照里 version 不是 22", Regex("\"version\"\\s*:\\s*22").containsMatchIn(text))
        assertTrue(
            "迁移加了列 `skippedProfiles`，但 v22 schema 快照里没有它",
            text.contains("\"columnName\": \"skippedProfiles\""),
        )
    }
}
