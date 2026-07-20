#!/usr/bin/env python3
"""ANEB campaign-analysis shared helpers (stdlib only, no third-party deps).

Shared foundation for the CAMPAIGN-LEVEL analysis & reporting layer:
  - attribution.py     三级(同城/区域/中心)差分归因矩阵
  - campaign_report.py 点位×忙闲×运营商热力卡 + 优化前后对比 + 综合报告

Reads server-side results JSONL (contract schema 1.0, same input as
analyze_results.py / dashboard.py). Field paths follow app/probe ResultReporter.kt:
top-level contract fields, `run.aqs.score`, `run.started_at_epoch_ms`,
`scenarios[].kpi.*`, `scenarios[].validity`. Campaign grouping labels are read
from the OPTIONAL additive `run.campaign` block — see docs/CAMPAIGN_LABELS_CONVENTION.md.

R-10 discipline: a missing label is NEVER coerced to a real value. It degrades to
an explicit "unlabeled"/"unknown" bucket (or None for tier — never guessed), so the
report can show a coverage gap instead of a fabricated cell.
"""
import glob
import json
import math
import statistics
import sys
from collections import Counter, defaultdict  # noqa: F401 (re-exported for consumers)

# ---- four-level grading colors (mirror dashboard.py / KpiGrading.kt) --------
GRADE_COLORS = {
    "excellent": ("#e6f4ea", "#137333"),
    "good":      ("#e8f0fe", "#1a56b0"),
    "fair":      ("#fef7e0", "#b06000"),
    "poor":      ("#fce8e6", "#c5221f"),
    "n/a":       ("#f5f5f5", "#444444"),
}
GRADE_ORDER = ["excellent", "good", "fair", "poor"]  # best -> worst

# ---- three server tiers (campaign labels convention §2/§3) ------------------
TIERS = ["metro", "regional", "core"]
TIER_LABELS = {"metro": "同城", "regional": "区域", "core": "中心"}
_TIER_ALIASES = {
    "metro": "metro", "同城": "metro", "local": "metro", "city": "metro",
    "regional": "regional", "区域": "regional", "region": "regional", "provincial": "regional",
    "core": "core", "中心": "core", "central": "core", "backbone": "core", "national": "core",
}
_CARRIER_ALIASES = {
    "cmcc": "cmcc", "移动": "cmcc", "chinamobile": "cmcc", "china mobile": "cmcc",
    "cucc": "cucc", "联通": "cucc", "chinaunicom": "cucc", "china unicom": "cucc",
    "ctcc": "ctcc", "电信": "ctcc", "chinatelecom": "ctcc", "china telecom": "ctcc",
}

DEFAULT_MIN_SAMPLES = 5   # per-tier / per-cell sample floor for low_confidence
# AQS 0-100 -> four-level presentation bands. Anchored to the system's known score
# caps: veto/S1<0.90 封顶 54, S1<0.95 封顶 70 (result-run.schema.json). Presentation
# only — NOT the authoritative per-KPI grading (that is KpiGrading.kt).
AQS_GRADE_BANDS = [(85.0, "excellent"), (70.0, "good"), (54.0, "fair"), (0.0, "poor")]


def force_utf8_stdout():
    """Make CLI stdout/stderr UTF-8 regardless of console codepage (Windows GBK
    can't encode e.g. U+26A0 ⚠). No-op where reconfigure is unavailable."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def fnum(v):
    """Numeric-or-None guard (bool excluded — JSON true/false are not measurements)."""
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def load_records(patterns):
    """Load JSONL records from files/globs. Returns (records, files). Tolerant of
    blank lines and malformed JSON (skipped with a stderr note)."""
    records, files = [], []
    for pat in patterns:
        paths = glob.glob(pat) or ([pat] if not any(c in pat for c in "*?[") else [])
        for path in paths:
            files.append(path)
            try:
                with open(path, encoding="utf-8") as f:
                    for lineno, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError as e:
                            print(f"skip {path}:{lineno}: {e}", file=sys.stderr)
            except OSError as e:
                print(f"skip {path}: {e}", file=sys.stderr)
    return records, files


# ---------------------------------------------------------------- accessors

def run_obj(rec):
    return rec.get("run") or {}


def run_aqs(rec):
    """run.aqs.score with legacy fallbacks (top-level aqs / aqs_result.score)."""
    aqs_obj = run_obj(rec).get("aqs") or {}
    v = fnum(aqs_obj.get("score"))
    if v is None:
        v = fnum(rec.get("aqs")) or fnum((rec.get("aqs_result") or {}).get("score"))
    return v


def run_started_ms(rec):
    return fnum(run_obj(rec).get("started_at_epoch_ms"))


def iter_scenarios(rec):
    return rec.get("scenarios") or []


def scenario_validity(scn):
    """Normalized lower-case validity (schema enum is upper-case, real records
    have been seen lower-case — normalize so both compare equal)."""
    v = scn.get("validity")
    return v.lower() if isinstance(v, str) else "unknown"


def scenario_kpi(scn, key):
    """scenarios[].kpi.<key> as a number or None. Accepts legacy `kpis` and
    {value: x} nesting."""
    kpi = scn.get("kpi") or scn.get("kpis") or {}
    v = kpi.get(key)
    if isinstance(v, dict):
        v = v.get("value")
    return fnum(v)


# ---------------------------------------------------------------- campaign labels

def _canon(value, aliases):
    if not isinstance(value, str):
        return None
    return aliases.get(value.strip().lower(), value.strip().lower())


def campaign_labels(rec):
    """Extract grouping labels from the OPTIONAL run.campaign block, with graceful
    degradation (docs/CAMPAIGN_LABELS_CONVENTION.md §2.1). tier stays None when
    absent/unrecognized (never guessed); the rest degrade to explicit buckets."""
    c = run_obj(rec).get("campaign") or {}
    tier = _canon(c.get("tier"), _TIER_ALIASES)
    if tier not in TIERS:
        tier = None  # unknown tier -> excluded from attribution, recorded as coverage gap
    carrier = _canon(c.get("carrier"), _CARRIER_ALIASES) or "unknown"
    time_band = c.get("time_band")
    return {
        "campaign_id": c.get("campaign_id") or "unlabeled",
        "tier": tier,
        "point_id": c.get("point_id") or "unlabeled",
        "carrier": carrier,
        "time_band": time_band.strip().lower() if isinstance(time_band, str) and time_band.strip()
        else "unknown",
    }


# ---------------------------------------------------------------- stats

def median(vals):
    vals = [v for v in vals if v is not None]
    return statistics.median(vals) if vals else None


def mean(vals):
    vals = [v for v in vals if v is not None]
    return statistics.fmean(vals) if vals else None


def percentile(vals, p):
    """Nearest-rank percentile (repo convention; matches KPI percentile handling).
    p in [0,100]. Returns None on empty input."""
    xs = sorted(v for v in vals if v is not None)
    if not xs:
        return None
    if p <= 0:
        return xs[0]
    if p >= 100:
        return xs[-1]
    rank = math.ceil(p / 100.0 * len(xs))  # 1-indexed nearest-rank
    return xs[max(1, rank) - 1]


def aqs_grade(score, bands=AQS_GRADE_BANDS):
    """Map an AQS 0-100 score to a four-level presentation grade. None -> 'n/a'."""
    if score is None:
        return "n/a"
    for threshold, name in bands:
        if score >= threshold:
            return name
    return "poor"


def fmt_num(v, digits=1):
    if v is None:
        return "—"
    s = f"{v:.{digits}f}"
    return s.rstrip("0").rstrip(".") if "." in s else s
