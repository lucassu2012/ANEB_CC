package com.aneb.probe.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * DB v23 迁移合同单测（A-8③ 构建指纹 ＋ C-6 溯源列，**两件合并成一版**，D-719②）。
 *
 * 纪律承 [MigrationV22Test]，但本版与前几版有一处结构性不同：
 * **它一次动两张表**（`test_run` 三列、`adapter_obs` 三列）。因此下面的断言不能只数
 * 「一共几条语句」——那种写法在「六条全打到同一张表」时照样通过，而那是个真实存在的
 * 打字错误形态（复制粘贴改了列名忘了改表名）。**逐表分别核，并核每表的列集合。**
 *
 * ⚠ **本版定义被修订过一次（D-729，加第七条 `injectUsed`），当时的前提是「无任何设备
 * 装过 v23」**——`.ctree` 上仍是 v22 库、无人重装，故改迁移定义本身是安全的。
 * **这个前提必须与事实一起记住**：一旦有设备已按旧定义迁到 v23，再改本列表就
 * **不是修订而是伪造**——那些设备的库里少一列而版本号说它是 v23，Room 下次打开即抛
 * schema 不匹配，且**没有任何迁移路径能补救**。届时正确做法是发 v24，不是动这里。
 *
 * ⚠ **`adapter_obs` 那三列本批只有列、没有写入逻辑**（C-6 的 `enqueuePersist` 分列、
 * 定时 emit、IME 监听等未做）⇒ 迁移后恒为 null。本测试**只锚迁移合同，不断言数据在采**
 * ——「列已存在」推不出「数据已在采」。
 */
class MigrationV23Test {

    /** 从模块工作目录（`app/probe`）向上找仓库根相对路径（同 [MigrationV22Test]）。 */
    private fun repoFile(relFromRepoRoot: String): File {
        var cur: File? = File(System.getProperty("user.dir") ?: ".").absoluteFile
        while (cur != null) {
            val cand = File(cur, relFromRepoRoot)
            if (cand.isFile) return cand
            cur = cur.parentFile
        }
        error("找不到 $relFromRepoRoot（从 user.dir 向上未命中）")
    }

    private val sql get() = AnebDatabase.MIGRATION_22_23_SQL

    /** 解析出 (表名, 列名)；任一条不合 `ALTER TABLE ... ADD COLUMN` 形状即判失败。 */
    private fun tableAndColumn(stmt: String): Pair<String, String> {
        val m = Regex("ALTER TABLE `([^`]+)` ADD COLUMN `([^`]+)`").find(stmt)
        assertTrue("非 additive 加列语句: $stmt", m != null)
        return m!!.groupValues[1] to m.groupValues[2]
    }

    @Test
    fun migrationVersionsAre22To23() {
        assertEquals(22, AnebDatabase.MIGRATION_22_23.startVersion)
        assertEquals(23, AnebDatabase.MIGRATION_22_23.endVersion)
    }

    /**
     * 六条语句、两张表、每表三列——**逐表核集合，不只数总数**。
     * 只数总数的话，「六条全打到 test_run」会通过，而那正是改列名忘改表名的形状。
     */
    @Test
    fun addsSevenColumnsAcrossExactlyTwoTables() {
        assertEquals("v23 应为七条 additive 语句", 7, sql.size)
        val byTable = sql.map { tableAndColumn(it) }
            .groupBy({ it.first }, { it.second })
            .mapValues { it.value.toSet() }

        assertEquals("应恰好动两张表", setOf("test_run", "adapter_obs"), byTable.keys)
        assertEquals(
            "test_run 的四列（构建指纹三 ＋ 注入标记一）不符",
            setOf("buildGitSha", "buildType", "buildApplicationId", "injectUsed"),
            byTable["test_run"],
        )
        assertEquals(
            "adapter_obs 的溯源三列不符",
            setOf("ttftSource", "ttftDensityMs", "targetVersionCode"),
            byTable["adapter_obs"],
        )
    }

    /** additive-only：不得破坏性、不得 NOT NULL、不得带默认值（R-10：缺失 ≠ 已知值）。 */
    @Test
    fun everyStatementIsAdditiveAndNullable() {
        for (stmt in sql) {
            val upper = stmt.uppercase()
            assertTrue(
                "破坏性语句: $stmt",
                !upper.contains("DROP TABLE") && !upper.contains("DROP COLUMN") &&
                    !upper.contains("DELETE FROM") && !upper.contains("UPDATE "),
            )
            assertTrue("新列不得 NOT NULL（R-10 可空）: $stmt", !upper.contains("NOT NULL"))
            assertTrue(
                "新列不得带默认值——有默认值就分不出「早于本列上线」与「测到了这个值」: $stmt",
                !upper.contains("DEFAULT"),
            )
        }
    }

    /**
     * 列的 SQLite affinity 必须与实体字段的 Kotlin 类型对得上。
     * 写错不会在 JVM 层报错，**要到真机 Room 校验 schema 时才炸**——最晚最贵的发现时机。
     */
    @Test
    fun columnAffinitiesMatchTheKotlinTypes() {
        val expected = mapOf(
            "buildGitSha" to "TEXT",
            "buildType" to "TEXT",
            "buildApplicationId" to "TEXT",
            "injectUsed" to "INTEGER", // Boolean? —— SQLite 无布尔类型
            "ttftSource" to "TEXT",
            "ttftDensityMs" to "REAL", // Double?
            "targetVersionCode" to "INTEGER", // Long?
        )
        for (stmt in sql) {
            val (_, col) = tableAndColumn(stmt)
            val want = expected[col] ?: error("未预期的列 $col")
            assertTrue("列 `$col` 的 affinity 应为 $want: $stmt", stmt.uppercase().endsWith(" $want"))
        }
    }

    /**
     * 迁移列名必须与实体字段名逐字一致——两张表**分别**核。
     * Room 只在真机启动时 fail-fast，JVM 层不核就一路绿到设备上。
     */
    @Test
    fun migrationColumnNamesMatchEntityFieldNames() {
        val testRunFields = TestRun::class.java.declaredFields.map { it.name }.toSet()
        val obsFields = AdapterObsEntity::class.java.declaredFields.map { it.name }.toSet()
        for (stmt in sql) {
            val (table, col) = tableAndColumn(stmt)
            val fields = when (table) {
                "test_run" -> testRunFields
                "adapter_obs" -> obsFields
                else -> error("未预期的表 $table")
            }
            assertTrue(
                "迁移列 `$col` 在 $table 对应实体里没有同名字段——Room 会在真机启动时炸",
                fields.contains(col),
            )
        }
    }

    /**
     * 六列必须都真的落进 Room 导出的 schema 快照。
     * ⚠ 承 V21 引入的纪律：**快照缺列时上面几条照样全绿**——它们只读迁移 SQL 这一侧，
     * 而真机升级校验的是快照那一侧。两侧分开验，才拦得住「SQL 写了但实体没加」这类漂移。
     */
    @Test
    fun theExportedSchemaSnapshotCarriesAllSixColumns() {
        val snapshot = repoFile("app/probe/schemas/com.aneb.probe.data.AnebDatabase/23.json")
        val text = snapshot.readText()
        assertTrue("快照里 version 不是 23", Regex("\"version\"\\s*:\\s*23").containsMatchIn(text))
        for (stmt in sql) {
            val (_, col) = tableAndColumn(stmt)
            assertTrue(
                "迁移加了列 `$col`，但 v23 schema 快照里没有它",
                text.contains("\"columnName\": \"$col\""),
            )
        }
    }
}
