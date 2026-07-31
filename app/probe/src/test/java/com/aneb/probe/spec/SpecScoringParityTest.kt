package com.aneb.probe.spec

import com.aneb.probe.scoring.AqsScorer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * spec/scoring 三份 YAML(weights/anchors/vetoes)↔ AqsScorer 一致性对拍
 * (铁律 1 治理面;spec/README.md「导出+对拍」条款)。
 *
 * 本轮代码**不反向引用** YAML(避免大改打分链风险),防漂移全靠本测试:
 * - 代码侧全集经反射枚举(WEIGHTS* 权重表字段 / AnchorMap 锚点表字段 / *VETO* double 常量)
 *   —— **任何一侧新增/删除/改值而另一侧未跟进即红**;
 * - 锚点对拍不读 AnchorMap 私有列表,走行为三重对拍:逐锚点 score(x)==y、相邻锚点中点
 *   线性插值一致(捕获代码侧多/少锚点)、越界 clamp 到端点分;
 * - YAML 解析用测试内嵌的受控子集解析器 [MiniYaml](spec 生成侧保证只用该子集),不加库依赖。
 *
 * spec 文件缺失即红(spec 与代码必须同步提交,不 Assume 跳过)。
 */
class SpecScoringParityTest {

    // ---------- spec 文件定位(自模块工作目录向上找仓根 spec/scoring;可 -Daneb.spec.dir 覆盖) ----------

    private fun specScoringDir(): File {
        System.getProperty("aneb.spec.dir")?.let { p ->
            val f = File(p)
            if (f.isDirectory) return f
        }
        var cur: File? = File(System.getProperty("user.dir") ?: ".").absoluteFile
        repeat(8) {
            val cand = File(cur, "spec/scoring")
            if (cand.isDirectory) return cand
            cur = cur?.parentFile
            if (cur == null) throw AssertionError("找不到 spec/scoring 目录(user.dir 向上已到根)")
        }
        throw AssertionError("找不到 spec/scoring 目录(user.dir 向上 8 级未命中)")
    }

    private fun loadYaml(name: String): Map<String, Any> {
        val f = File(specScoringDir(), name)
        assertTrue("spec/scoring/$name 缺失——spec 与代码必须同步提交", f.isFile)
        return MiniYaml.parse(f.readLines(Charsets.UTF_8))
    }

    @Suppress("UNCHECKED_CAST")
    private fun node(m: Map<String, Any>, key: String): Map<String, Any> =
        m[key] as? Map<String, Any> ?: throw AssertionError("YAML 缺映射节点: $key")

    private fun scalar(m: Map<String, Any>, key: String): String =
        m[key] as? String ?: throw AssertionError("YAML 缺标量: $key")

    private fun num(m: Map<String, Any>, key: String): Double = scalar(m, key).toDouble()

    // ---------- 代码侧全集(反射枚举:新增表/常量而 spec 未跟进即集合断言红) ----------

    /** AqsScorer 全部权重表字段(WEIGHTS 前缀 + Map 类型;TOKEN_WEIGHT_TABLES 为注册表不在此列)。 */
    @Suppress("UNCHECKED_CAST")
    private fun codeWeightTables(): Map<String, Map<String, Double>> =
        AqsScorer.javaClass.declaredFields
            .filter { it.name.startsWith("WEIGHTS") && Map::class.java.isAssignableFrom(it.type) }
            .associate { f ->
                f.isAccessible = true
                f.name to (f.get(AqsScorer) as Map<String, Double>)
            }

    /** AqsScorer 全部锚点表字段(AnchorMap 类型);键 = 字段名去 "_ANCHORS" 后缀(anchors.yaml 表名约定)。 */
    private fun codeAnchorTables(): Map<String, AqsScorer.AnchorMap> =
        AqsScorer.javaClass.declaredFields
            .filter { it.type == AqsScorer.AnchorMap::class.java }
            .associate { f ->
                f.isAccessible = true
                f.name.removeSuffix("_ANCHORS") to (f.get(AqsScorer) as AqsScorer.AnchorMap)
            }

    /** AqsScorer 全部否决常量(名含 VETO 的 double)。 */
    private fun codeVetoConstants(): Map<String, Double> =
        AqsScorer.javaClass.declaredFields
            .filter { it.name.contains("VETO") && it.type == java.lang.Double.TYPE }
            .associate { f ->
                f.isAccessible = true
                f.name to f.getDouble(AqsScorer)
            }

    // ---------- 用例 1:权重表全量对拍 ----------

    @Test
    fun weights_tables_full_parity() {
        val tables = node(loadYaml("weights.yaml"), "tables")
        val code = codeWeightTables()
        assertEquals(
            "权重表集合漂移(AqsScorer WEIGHTS* 字段 vs spec/scoring/weights.yaml tables)",
            code.keys.sorted(), tables.keys.sorted(),
        )
        for ((name, codeTable) in code) {
            val specWeights = node(node(tables, name), "weights")
            assertEquals("[$name] KPI 键集漂移", codeTable.keys.sorted(), specWeights.keys.sorted())
            for ((kpi, w) in codeTable) {
                assertEquals("[$name.$kpi] 权重值漂移", w, num(specWeights, kpi), 1e-9)
            }
            assertEquals("[$name] Σ权重 ≠ 1.0", 1.0, codeTable.values.sum(), 1e-9)
        }
    }

    // ---------- 用例 2:锚点表全量对拍(逐锚点 + 中点插值 + 越界 clamp + 方向) ----------

    @Test
    fun anchors_full_parity() {
        val yaml = loadYaml("anchors.yaml")
        val anchors = node(yaml, "anchors")
        val code = codeAnchorTables()
        assertEquals(
            "锚点表集合漂移(AqsScorer *_ANCHORS 字段 vs spec/scoring/anchors.yaml anchors)",
            code.keys.sorted(), anchors.keys.sorted(),
        )
        for ((name, anchorMap) in code) {
            val spec = node(anchors, name)
            @Suppress("UNCHECKED_CAST")
            val pts = spec["points"] as? List<List<Double>> ?: throw AssertionError("[$name] 缺 points 列表")
            assertTrue("[$name] 锚点数必须 ≥2", pts.size >= 2)
            // 1) 逐锚点:score(x) == y
            for (p in pts) {
                assertEquals("[$name] 锚点(${p[0]})分值漂移", p[1], anchorMap.score(p[0]), 1e-6)
            }
            // 2) 相邻锚点中点线性插值一致(捕获代码侧多/少/移位锚点)
            for (i in 1 until pts.size) {
                val x0 = pts[i - 1][0]; val y0 = pts[i - 1][1]
                val x1 = pts[i][0]; val y1 = pts[i][1]
                val mid = (x0 + x1) / 2.0
                val expected = y0 + (mid - x0) / (x1 - x0) * (y1 - y0)
                assertEquals("[$name] 中点($mid)插值漂移", expected, anchorMap.score(mid), 1e-6)
            }
            // 3) 越界 clamp 到端点分
            assertEquals("[$name] 下界外 clamp 漂移", pts.first()[1], anchorMap.score(pts.first()[0] - 1.0), 1e-6)
            assertEquals("[$name] 上界外 clamp 漂移", pts.last()[1], anchorMap.score(pts.last()[0] + 1.0), 1e-6)
            // 4) direction 声明与端点分走向一致
            val expectDir = if (pts.first()[1] > pts.last()[1]) "lower_better" else "higher_better"
            assertEquals("[$name] direction 声明漂移", expectDir, scalar(spec, "direction"))
        }
    }

    // ---------- 用例 3:否决参数对拍(常量全集覆盖 + 逐值) ----------

    @Test
    fun veto_constants_parity() {
        val vetoes = node(loadYaml("vetoes.yaml"), "vetoes")
        // spec 条目 → 代码常量映射(threshold 常量名, cap 常量名);
        // M1 的 cap 复用 T4_VETO_CAP(代码 scoreWith: if (veto) total = min(total, T4_VETO_CAP))
        val mapping = mapOf(
            "T4" to ("T4_VETO_THRESHOLD" to "T4_VETO_CAP"),
            "S1_SOFT" to ("S1_VETO_SOFT_THRESHOLD" to "S1_VETO_SOFT_CAP"),
            "S1_HARD" to ("S1_VETO_HARD_THRESHOLD" to "S1_VETO_HARD_CAP"),
            "M1" to ("M1_VETO_THRESHOLD_MS" to "T4_VETO_CAP"),
        )
        val consts = codeVetoConstants()
        assertEquals(
            "AqsScorer 否决常量全集漂移(新增/删除 *VETO* 常量须同步 spec/scoring/vetoes.yaml)",
            mapping.values.flatMap { listOf(it.first, it.second) }.toSortedSet().toList(),
            consts.keys.toSortedSet().toList(),
        )
        assertEquals("vetoes.yaml 条目集漂移", mapping.keys.sorted(), vetoes.keys.sorted())
        for ((entry, pair) in mapping) {
            val spec = node(vetoes, entry)
            assertEquals("[$entry] threshold 漂移", consts.getValue(pair.first), num(spec, "threshold"), 1e-9)
            assertEquals("[$entry] cap 漂移", consts.getValue(pair.second), num(spec, "cap"), 1e-9)
        }
    }

    // ---------- 用例 4:无线分档阈值对拍(RADIO_CONTEXT_WIRING_SPEC §5,D-367) ----------

    @Test
    fun radio_bands_parity() {
        val bands = node(loadYaml("radio_bands.yaml"), "bands")
        // 代码侧全集经反射枚举(BufferingDetector 的 RSRP_/SINR_ double 常量):
        // 任一侧新增/删除/改值而另一侧未跟进即红(同 veto_constants_parity 套路)。
        // 分析层的抄本(campaign_common)由其自己的守卫对账同一份 YAML——两辐条一轮毂。
        val det = com.aneb.probe.scoring.BufferingDetector
        val consts = det.javaClass.declaredFields
            .filter {
                (it.name.startsWith("RSRP_") || it.name.startsWith("SINR_")) &&
                    it.type == java.lang.Double.TYPE
            }
            .associate { f ->
                f.isAccessible = true
                f.name.lowercase() to f.getDouble(det)
            }
        assertEquals(
            "BufferingDetector 信号阈值全集漂移(新增/删除 RSRP_/SINR_ 常量须同步 spec/scoring/radio_bands.yaml)",
            consts.keys.sorted(),
            bands.keys.sorted(),
        )
        for ((key, value) in consts) {
            assertEquals("[$key] 阈值漂移", value, num(bands, key), 1e-9)
        }
    }

    // ---------- 用例 4:版本 id 对拍(权重表 version_id + kpi_set_version + spec 起版) ----------

    @Test
    fun version_ids_parity() {
        val weightsYaml = loadYaml("weights.yaml")
        val tables = node(weightsYaml, "tables")
        val expected = mapOf(
            "WEIGHTS" to AqsScorer.AQS_VERSION,
            "WEIGHTS_V02" to AqsScorer.AQS_VERSION_V02,
            "WEIGHTS_TOKEN_MM" to AqsScorer.AQS_VERSION_TOKEN,
            "WEIGHTS_TOKEN_TXT" to AqsScorer.AQS_VERSION_TOKEN,
            "WEIGHTS_VOICE" to AqsScorer.AQS_VERSION_VOICE,
            "WEIGHTS_VOICE_SIM" to AqsScorer.AQS_VERSION_VOICE_SIM,
        )
        assertEquals("version_id 映射覆盖漂移(新增权重表须补映射)", expected.keys.sorted(), tables.keys.sorted())
        for ((name, ver) in expected) {
            assertEquals("[$name] version_id 漂移", ver, scalar(node(tables, name), "version_id"))
        }
        val anchorsYaml = loadYaml("anchors.yaml")
        assertEquals("kpi_set_version 漂移", AqsScorer.KPI_SET_VERSION, scalar(anchorsYaml, "kpi_set_version"))
        // spec 起版 1.0.0(spec/README.md 语义化版本条款)
        assertEquals("weights.yaml schema_version 起版", "1.0.0", scalar(weightsYaml, "schema_version"))
        assertEquals("anchors.yaml schema_version 起版", "1.0.0", scalar(anchorsYaml, "schema_version"))
        assertEquals("vetoes.yaml schema_version 起版", "1.0.0", scalar(loadYaml("vetoes.yaml"), "schema_version"))
    }
}

/**
 * 受控 YAML 子集解析器(仅供本对拍测试解析 spec/scoring 下三份 YAML;**勿加库依赖**的裁定实现):
 * - 2 空格缩进的嵌套映射;
 * - 标量 `key: value`(去首尾引号,一律返回 String,数值由调用方转换);
 * - 数值对列表项 `- [a, b]`(返回 List<Double>,恰 2 元);
 * - 整行注释(#)与空行忽略;不支持行内注释/流式映射/多行标量。
 * spec 生成侧(本仓)保证只使用该子集;超集语法出现即抛错(fail-closed,防静默误读)。
 */
private object MiniYaml {

    fun parse(rawLines: List<String>): Map<String, Any> {
        val lines = rawLines.filter { it.isNotBlank() && !it.trimStart().startsWith("#") }
        require(lines.isNotEmpty()) { "空 YAML" }
        val (value, next) = parseBlock(lines, 0, 0)
        require(next == lines.size) { "解析未消费全部行: $next/${lines.size}" }
        @Suppress("UNCHECKED_CAST")
        return value as Map<String, Any>
    }

    private fun indentOf(line: String): Int = line.length - line.trimStart().length

    /** 解析从 [start] 开始、缩进恰为 [indent] 的块;返回 (值, 下一未消费行号)。 */
    private fun parseBlock(lines: List<String>, start: Int, indent: Int): Pair<Any, Int> =
        if (lines[start].trimStart().startsWith("- ")) parseList(lines, start, indent)
        else parseMap(lines, start, indent)

    private fun parseList(lines: List<String>, start: Int, indent: Int): Pair<Any, Int> {
        val items = mutableListOf<List<Double>>()
        var i = start
        while (i < lines.size && indentOf(lines[i]) == indent && lines[i].trimStart().startsWith("- ")) {
            val body = lines[i].trimStart().removePrefix("- ").trim()
            require(body.startsWith("[") && body.endsWith("]")) { "仅支持 `- [a, b]` 列表项: $body" }
            val nums = body.removePrefix("[").removeSuffix("]").split(",").map { it.trim().toDouble() }
            require(nums.size == 2) { "锚点对必须恰为 2 元: $body" }
            items.add(nums)
            i++
        }
        return items to i
    }

    private fun parseMap(lines: List<String>, start: Int, indent: Int): Pair<Any, Int> {
        val map = LinkedHashMap<String, Any>()
        var i = start
        while (i < lines.size) {
            val ind = indentOf(lines[i])
            if (ind < indent) break
            require(ind == indent) { "缩进异常(期望 $indent): ${lines[i]}" }
            val t = lines[i].trimStart()
            require(!t.startsWith("- ")) { "映射块内出现列表项: $t" }
            val colon = t.indexOf(':')
            require(colon > 0) { "非 `key: value` 行: $t" }
            val key = t.substring(0, colon).trim()
            val rest = t.substring(colon + 1).trim()
            if (rest.isEmpty()) {
                require(i + 1 < lines.size && indentOf(lines[i + 1]) > indent) { "空块: $key" }
                val (child, next) = parseBlock(lines, i + 1, indentOf(lines[i + 1]))
                map[key] = child
                i = next
            } else {
                map[key] = rest.removeSurrounding("\"").removeSurrounding("'")
                i++
            }
        }
        return map to i
    }
}
