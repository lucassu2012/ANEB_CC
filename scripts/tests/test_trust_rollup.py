# -*- coding: utf-8 -*-
"""Golden reflex tests for scripts/trust_rollup.py (instrument trust)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # scripts/tests/

import trust_rollup as tu
from synth import make_record


def _rec(*, clock=None, kpi=None, parse=None, point="P1"):
    rec = make_record(
        campaign={"campaign_id": "base", "tier": "metro", "point_id": point,
                  "carrier": "cmcc", "time_band": "busy"},
        aqs=90, scenarios=[("s1_chat", dict(kpi or {}))])
    scn = rec["scenarios"][0]
    if clock is not None:
        scn["clock"] = clock
    if parse is not None:
        scn["parse"] = parse
    return rec


def test_suspect_share_and_abs_drift():
    recs = ([_rec(clock={"offset_suspect": True, "drift_ppm": -150.0}) for _ in range(3)]
            + [_rec(clock={"offset_suspect": False, "drift_ppm": 10.0}) for _ in range(2)])
    c = tu.analyze(recs)["cells"][0]
    assert c["clock_annotated"] == 5
    assert c["clock_suspect"] == 3
    assert c["clock_suspect_share"] == 0.6
    assert c["abs_drift_ppm_median"] == 150.0      # |-150| median of [150,150,150,10,10]
    assert c["clock_hotspot"] is True


def test_unannotated_clock_not_counted_as_clean():
    recs = [_rec(clock={"offset_suspect": True, "drift_ppm": 200.0})] \
        + [_rec() for _ in range(4)]               # empty clock {} = unannotated
    c = tu.analyze(recs)["cells"][0]
    assert c["clock_annotated"] == 1               # denominators exclude unannotated
    assert c["clock_suspect_share"] == 1.0
    assert c["clock_hotspot"] is True              # of ANNOTATED clocks, all suspect


def test_exactly_half_suspect_is_not_hotspot():
    recs = ([_rec(clock={"offset_suspect": True}) for _ in range(2)]
            + [_rec(clock={"offset_suspect": False}) for _ in range(2)])
    assert tu.analyze(recs)["cells"][0]["clock_hotspot"] is False


# ------------------------------------------------------- 低置信定位（D-373）

def _rec_quality(quality):
    rec = _rec(clock={"offset_suspect": False})
    rec["scenarios"][0]["kpi_quality"] = quality
    return rec


def test_kpi_quality_rollup_names_which_kpi_is_short_and_by_how_much():
    """试点报告附二第一建议的读者半边:低置信判词带上理由——哪个 KPI、
    低置信几次、最少几个样本。两半都钉:被标注的行与干净的行。"""
    recs = [_rec_quality({"U2": {"sample_count": 5, "low_confidence": True},
                          "N1": {"sample_count": 20, "low_confidence": False}})
            for _ in range(3)]
    res = tu.analyze(recs)
    kq = res["kpi_quality"]
    assert kq["U2"] == {"annotated": 3, "low": 3, "min_n": 5}, kq
    assert kq["N1"] == {"annotated": 3, "low": 0, "min_n": 20}, kq
    md = tu.render_markdown(res)
    assert "低置信定位" in md
    assert "| U2 | 3 | 3 (100%) | 5 |" in md, md
    assert "| N1 | 3 | 0 (0%) | 20 |" in md, md


def test_a_corpus_without_kpi_quality_reports_a_gap_not_silence():
    """v17 之前的语料没有 kpi_quality:定位段必须说「无法定位」,
    而不是消失或渲染一张空表读成「没有低置信」(缺席≠全好,R-10)。"""
    res = tu.analyze([_rec(clock={"offset_suspect": False})])
    assert res["kpi_quality"] == {}
    md = tu.render_markdown(res)
    assert "无法定位" in md and "不等于没有" in md, md


def test_stream_bad_on_gap_or_dup():
    recs = [_rec(kpi={"seq_gap_count": 1, "seq_dup_count": 0}),
            _rec(kpi={"seq_gap_count": 0, "seq_dup_count": 2}),
            _rec(kpi={"seq_gap_count": 0, "seq_dup_count": 0})]
    c = tu.analyze(recs)["cells"][0]
    assert c["stream_counted"] == 3
    assert c["stream_bad"] == 2


def test_null_seq_counts_not_in_denominator():
    recs = [_rec(kpi={"seq_gap_count": None, "seq_dup_count": None}),
            _rec(kpi={"seq_gap_count": 0, "seq_dup_count": 0})]
    c = tu.analyze(recs)["cells"][0]
    assert c["stream_counted"] == 1                # null = not measured, not clean


def test_parse_median():
    recs = [_rec(parse={"per_event_parse_us": v}) for v in (10, 42, 100)]
    assert tu.analyze(recs)["cells"][0]["parse_per_event_us_median"] == 42


def test_no_evidence_renders_coverage_gap():
    md = tu.render_markdown(tu.analyze([_rec() for _ in range(3)]))
    assert "无可信度证据" in md
    assert "非全部可信" in md


def test_markdown_renders_r22_and_hotspot():
    recs = [_rec(clock={"offset_suspect": True, "drift_ppm": 200.0}) for _ in range(5)]
    md = tu.render_markdown(tu.analyze(recs))
    assert "R-22" in md
    assert "时钟可疑热点" in md
    assert "不算干净" in md


def test_cells_separated_by_point():
    recs = ([_rec(clock={"offset_suspect": True}, point="P1") for _ in range(2)]
            + [_rec(clock={"offset_suspect": False}, point="P2") for _ in range(2)])
    by = {c["cell"]["point_id"]: c for c in tu.analyze(recs)["cells"]}
    assert by["P1"]["clock_hotspot"] is True
    assert by["P2"]["clock_hotspot"] is False


# ---- 墙钟门（D-506/T68）。判据 = |wall_skew_ms| > 60s，标记非否决 ----

def test_wall_skew_threshold_is_a_boundary_not_a_ballpark():
    """恰好等于阈值不算可疑，越过一毫秒才算——严格 `>`，与设备侧同判据。

    D-535 的教训：'恰好等于临界'在浮点下没有普遍意义，故这里用整数毫秒钉两侧。
    """
    assert tu.wall_clock_suspect(tu.WALL_SKEW_MAX_MS) is False
    assert tu.wall_clock_suspect(tu.WALL_SKEW_MAX_MS + 1) is True
    # 负偏差同样算——设备钟快了和慢了一样毁掉"哪天测的"
    assert tu.wall_clock_suspect(-(tu.WALL_SKEW_MAX_MS + 1)) is True
    assert tu.wall_clock_suspect(-tu.WALL_SKEW_MAX_MS) is False


def test_missing_skew_is_not_suspect_and_not_clean():
    """缺证据 ⇒ 不判疑（False），但也**不计入分母**——不能被读成'干净'。

    这正是 EchoWire 接线前的语料形状：带 offset_suspect 却不带 wall_skew_ms。
    若共用时钟的分母，'没测'会被渲染成'测了且没问题'。
    """
    assert tu.wall_clock_suspect(None) is False
    recs = [_rec(clock={"offset_suspect": False, "drift_ppm": 1.0}) for _ in range(3)]
    cell = tu.analyze(recs)["cells"][0]
    assert cell["clock_annotated"] == 3      # 时钟侧有标注
    assert cell["wall_annotated"] == 0       # 墙钟侧没有——分母各自独立
    assert cell["wall_suspect"] == 0
    assert cell["wall_suspect_share"] is None    # 不是 0.0，是"无从判断"
    assert cell["abs_wall_skew_ms_median"] is None


def test_wall_suspect_is_marked_never_vetoed():
    """标记非否决（D-506）：墙钟可疑不影响任何既有判定，只多一行点名。"""
    recs = ([_rec(clock={"offset_suspect": False, "wall_skew_ms": 8_640_000})]
            + [_rec(clock={"offset_suspect": False, "wall_skew_ms": 12}) for _ in range(2)])
    res = tu.analyze(recs)
    cell = res["cells"][0]
    assert cell["wall_annotated"] == 3
    assert cell["wall_suspect"] == 1
    # 没有把整格判脏：时钟侧仍然干净，热点标记不受墙钟影响
    assert cell["clock_suspect"] == 0
    assert cell["clock_hotspot"] is False
    md = tu.render_markdown(res)
    assert "墙钟可疑 1 条" in md
    assert "服务端锚为准" in md          # 处置写在读者看得见的地方
    assert "标记非否决" in md


def test_wall_only_corpus_is_not_reported_as_no_evidence():
    """只有墙钟证据的语料，不能被判成'无可信度证据'。

    反例证伪：把 wall_annotated 从 no_evidence 判据里去掉，本条即红。
    """
    recs = [_rec(clock={"wall_skew_ms": 5}) for _ in range(3)]
    res = tu.analyze(recs)
    assert res["no_evidence"] is False
    assert "无可信度证据" not in tu.render_markdown(res)


def test_python_threshold_matches_the_kotlin_constant():
    """跨端一致性：本侧常量是 AnebClient.WALL_SKEW_MAX_MS 的副本，必须逐字相等。

    副本是不得已——设备侧算得出 wallClockSuspect() 却没把那个 bool 落进 wire，
    分析层只能拿阈值重算（见 trust_rollup 顶部注释）。既然是副本，就用**从产物
    导出**的方式钉住：直接抽 Kotlin 源码里的字面量，任一侧改动本条即红。
    """
    import re
    src = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "app", "probe", "src", "main", "java", "com", "aneb", "probe", "net", "AnebClient.kt")
    if not os.path.exists(src):          # 无 app 树的检出（分析层可独立使用）
        return
    with open(src, encoding="utf-8") as f:
        m = re.search(r"WALL_SKEW_MAX_MS\s*:\s*Long\s*=\s*([0-9_]+)L", f.read())
    assert m, "AnebClient.kt 里找不到 WALL_SKEW_MAX_MS——上游改名了，本侧副本失去锚点"
    assert int(m.group(1).replace("_", "")) == tu.WALL_SKEW_MAX_MS
