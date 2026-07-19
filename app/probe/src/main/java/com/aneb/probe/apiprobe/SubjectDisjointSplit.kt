package com.aneb.probe.apiprobe

/**
 * Token 校准数据集的**主体不重叠 train/holdout 划分**——纯 JVM（spine-1 任务 3，spine1 蓝图 §3.2）。
 *
 * 产出喂给 Codex `prepare-token-dataset` 的两份输入之一（training.jsonl / holdout.jsonl 的成员划分）：
 * 保 Codex 的 `subject_group_disjoint` 不变量（同一 subject 整体只入一侧）+ §4 逐 workload 计数下限
 * （train ≥ [minTrain] / holdout ≥ [minHoldout]）。**凑不齐则记 [Result.shortfalls]，不硬凑、不补哨兵**
 * （R-10 精神：数据不足如实暴露，绝不为达标伪造成员）。
 *
 * 本对象**不重定义** dataset-v1 manifest（那是 Codex 职责），只做成员分配；贪心确定性（subject id
 * 升序遍历，同输入同输出），非最优——满足约束即可，满足不了如实记 shortfall。
 */
object SubjectDisjointSplit {

    /** 已解析 observation 的最小三元组（分配只需这三字段）。 */
    data class ParsedObs(
        val observationId: String,
        val subjectGroupId: String,
        val workloadKind: String,
    )

    /**
     * @param training/holdout observation_id 列表（两分区零交集、各分区内唯一——由主体不重叠保证）
     * @param shortfalls 未达计数下限的 (workload, 分区) 清单（人读串；空=全部达标）
     */
    data class Result(
        val training: List<String>,
        val holdout: List<String>,
        val shortfalls: List<String>,
    )

    /**
     * 整主体贪心划分：subject id 升序遍历，若该 subject 覆盖的某 workload 在 holdout 侧仍未达
     * [minHoldout] 则整主体入 holdout，否则入 train；再逐 workload 核对 train/holdout 计数下限，
     * 未达者记 shortfall。空输入 → 空 Result。
     */
    fun assign(
        observations: List<ParsedObs>,
        minTrain: Int = 20,
        minHoldout: Int = 10,
    ): Result {
        val bySubject = observations.groupBy { it.subjectGroupId }
        val holdoutSubjects = LinkedHashSet<String>()
        val holdoutCounts = HashMap<String, Int>() // workload -> holdout 侧计数
        for (sid in bySubject.keys.sorted()) { // 确定性遍历
            val subjObs = bySubject.getValue(sid)
            val coversDeficient = subjObs.any { (holdoutCounts[it.workloadKind] ?: 0) < minHoldout }
            if (coversDeficient) {
                holdoutSubjects += sid
                subjObs.forEach { holdoutCounts.merge(it.workloadKind, 1, Int::plus) }
            }
        }
        val training = observations.filter { it.subjectGroupId !in holdoutSubjects }
        val holdout = observations.filter { it.subjectGroupId in holdoutSubjects }

        val trainByW = training.groupingBy { it.workloadKind }.eachCount()
        val holdByW = holdout.groupingBy { it.workloadKind }.eachCount()
        val shortfalls = mutableListOf<String>()
        for (w in observations.map { it.workloadKind }.toSortedSet()) {
            val t = trainByW[w] ?: 0
            val h = holdByW[w] ?: 0
            if (t < minTrain) shortfalls += "$w: train $t < $minTrain"
            if (h < minHoldout) shortfalls += "$w: holdout $h < $minHoldout"
        }
        return Result(training.map { it.observationId }, holdout.map { it.observationId }, shortfalls)
    }
}
