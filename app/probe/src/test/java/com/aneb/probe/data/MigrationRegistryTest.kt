package com.aneb.probe.data

import androidx.room.migration.Migration
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * 迁移注册表完整性（T68，承 T67/D-514 守卫审计 G-2）。
 *
 * **这条测试要防的事故**：有人把 `@Database(version = N)` 往上加一档，却忘了写对应的
 * `MIGRATION_(N-1)_N`。此前这类疏漏**没有任何东西会喊**——13 份 `MigrationV8..V20Test`
 * 每份只断言**自己那一个**迁移的 startVersion/endVersion 与 SQL 字符串，
 * 谁都不负责「这些台阶连起来有没有断」和「最高台阶是不是等于当前版本号」。
 * 而漏注册的后果曾经是不可逆的（无参 `fallbackToDestructiveMigration()` 会静默毁库重建，
 * 已在同批修为窄口径；即便修好，漏注册也只会变成运行时抛异常，仍不如在单测里当场拦下）。
 *
 * **清单是派生的不是手写的**（D-275：手写清单会漏会过期）：
 * - 迁移集合 = 反射 `AnebDatabase.Companion` 上全部 [Migration] 类型的字段；
 * - 当前版本号 = `app/probe/schemas/<db>/N.json` 里最大的 N（`exportSchema = true` 的产物，
 *   已入库）。两侧都不写死数字，新增一档迁移时本测试自动跟着走。
 */
class MigrationRegistryTest {

    /** 反射取 companion 上声明的全部 Migration 常量（不手抄名字）。 */
    private fun declaredMigrations(): List<Migration> {
        // Kotlin 把 companion object 里 val 的**后备字段**生成为外部类的 static 字段，
        // 所以要反射 AnebDatabase::class.java 而不是 Companion 实例——
        // 这一点是首跑失败后实测出来的（反射 Companion 取到 0 个字段）。
        return AnebDatabase::class.java.declaredFields
            .filter { Migration::class.java.isAssignableFrom(it.type) }
            .map { it.isAccessible = true; it.get(null) as Migration }
    }

    /** 从模块工作目录向上找仓库根（同 VoiceExecutionPlanParityTest 惯例）。 */
    private fun repoDir(rel: String): File {
        var cur: File? = File(System.getProperty("user.dir") ?: ".").absoluteFile
        while (cur != null) {
            val cand = File(cur, rel)
            if (cand.isDirectory) return cand
            cur = cur.parentFile
        }
        error("找不到目录 $rel（从 user.dir 向上未命中）")
    }

    /** 当前 schema 版本 = 导出目录里最大的 N.json（exportSchema 产物，已入库）。 */
    private fun exportedSchemaVersion(): Int {
        val dir = repoDir("app/probe/schemas/com.aneb.probe.data.AnebDatabase")
        val versions = dir.listFiles()
            .orEmpty()
            .mapNotNull { it.name.removeSuffix(".json").toIntOrNull() }
        assertTrue("schema 导出目录里应至少有一个 N.json", versions.isNotEmpty())
        return versions.max()
    }

    @Test fun `迁移台阶自 v6 起连续无断档`() {
        val steps = declaredMigrations()
            .map { it.startVersion to it.endVersion }
            .sortedBy { it.first }
        assertTrue("应至少声明一条迁移", steps.isNotEmpty())

        assertEquals("最低台阶应自 v6 起（v6 以下走 fallbackToDestructiveMigrationFrom）", 6, steps.first().first)
        steps.forEach { (from, to) ->
            assertEquals("每条迁移应恰好跨一个版本：$from->$to", from + 1, to)
        }
        steps.zipWithNext().forEach { (a, b) ->
            assertEquals("台阶之间不允许断档：${a.second} 之后应接 ${a.second}->，实为 ${b.first}->", a.second, b.first)
        }
    }

    @Test fun `最高迁移台阶等于当前 schema 版本（防「加了版本忘了写迁移」）`() {
        val maxEnd = declaredMigrations().maxOf { it.endVersion }
        val schemaVersion = exportedSchemaVersion()
        assertEquals(
            "@Database 版本($schemaVersion) 与最高迁移台阶($maxEnd) 不一致——" +
                "多半是加了 version 却忘了注册 MIGRATION_${schemaVersion - 1}_$schemaVersion；" +
                "历史数据是取证资产，漏注册不可接受（见 AnebDatabase 兜底处注释）",
            schemaVersion,
            maxEnd,
        )
    }
}
