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
import re
import statistics
import sys
import unicodedata
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
# The contract's claim-scope red line (R-10). Any record declaring something else
# is NOT comparable with this corpus and must be surfaced, never silently pooled.
CLAIM_SCOPE = "application_end_to_end_to_probe_node"
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
    """Numeric-or-None guard (bool excluded — JSON true/false are not measurements).

    NaN and ±Infinity are rejected too (D-148). They are not JSON per the spec,
    but Python's json module accepts the bare literals by default, so a producer
    or a converting tool can put them in a corpus. Letting one through does not
    merely spoil its own cell: NaN poisons the sort, so `median([10, 20, NaN,
    40, 50])` is NaN — one bad value destroys the median of the four good ones.
    Not-a-measurement becomes not-computable, never a number.
    """
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return None
    return v if math.isfinite(v) else None


def modal(counter):
    """(winner, tied) for a Counter of categorical verdicts.

    `Counter.most_common(1)` breaks ties by insertion order, so the same corpus
    in a different file order hands back a different verdict — and a 50/50 split
    is not a mode anyway, it is two populations. A tie returns winner=None with
    the tied keys, so the caller reports "no single verdict" instead of coining
    one (R-10). Deterministic in every case (D-148).
    """
    if not counter:
        return None, []
    top = max(counter.values())
    tied = sorted(k for k, n in counter.items() if n == top)
    return (tied[0], []) if len(tied) == 1 else (None, tied)


def ranked(counter):
    """Counter items ordered by count desc, then key asc — a stable order for
    display lists, where `most_common()` would otherwise leak input order."""
    return sorted(counter.items(), key=lambda kv: (-kv[1], str(kv[0])))


def load_records(patterns, dedupe=True, stats=None, quiet=False):
    """Load JSONL records from files/globs. Returns (records, files).

    dedupe=True (DEFAULT) drops repeat `run.run_id` occurrences. The same run
    re-exported into overlapping globs (or D-09 dual-write files) would otherwise
    be counted twice into every median, heat-cell n, and attribution sample —
    silently INFLATING apparent confidence. First occurrence wins.

    A repeat whose body DIFFERS from the first is also dropped but recorded in
    stats['conflicts']: one run_id with two different bodies is a real data
    -integrity fault, not a benign re-export, and must never be averaged together.
    Records with no run_id cannot be deduped — they are kept and counted, never
    merged under a fabricated key (R-10).

    Pass a dict as `stats` to receive integrity counters. Tolerant of blank and
    malformed lines (skipped, counted, noted on stderr unless quiet).
    """
    records, files = [], []
    seen = {}           # run_id -> canonical serialization of first occurrence
    st = {"lines": 0, "kept": 0, "malformed": 0, "unreadable_files": 0,
          "duplicates": 0, "conflicts": [], "no_run_id": 0}
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
                        st["lines"] += 1
                        try:
                            rec = json.loads(line)
                        except json.JSONDecodeError as e:
                            st["malformed"] += 1
                            if not quiet:
                                print(f"skip {path}:{lineno}: {e}", file=sys.stderr)
                            continue
                        if dedupe:
                            rid = run_id(rec)
                            if rid is None:
                                st["no_run_id"] += 1
                            else:
                                canon = json.dumps(rec, sort_keys=True, ensure_ascii=False)
                                if rid in seen:
                                    st["duplicates"] += 1
                                    if seen[rid] != canon and rid not in st["conflicts"]:
                                        st["conflicts"].append(rid)
                                    continue
                                seen[rid] = canon
                        records.append(rec)
                        st["kept"] += 1
            except OSError as e:
                st["unreadable_files"] += 1
                if not quiet:
                    print(f"skip {path}: {e}", file=sys.stderr)
    if stats is not None:
        stats.update(st)
    return records, files


# ---------------------------------------------------------------- accessors

def run_obj(rec):
    return rec.get("run") or {}


def run_id(rec):
    """run.run_id — the de-duplication key. None when absent/blank (never
    fabricated: an unidentifiable run must not be merged with another)."""
    v = run_obj(rec).get("run_id")
    return v if isinstance(v, str) and v.strip() else None


def run_aqs_flags(rec):
    """(veto_applied, scorer_low_confidence) as declared by the scorer itself.

    `run.aqs.veto_applied` is the T4 veto: severe-stall rate > 1% caps the score
    at 54 (spec/scoring/vetoes.yaml; AqsScorer.kt raises the same flag for the
    voice-only M1 mouth-to-ear red line, same cap). 54 is exactly a grade-band
    edge, so a capped run lands on the boundary and a cell pooling capped with
    uncapped runs has a median that characterises neither.

    NOT the session-success veto. S1 (<0.95 -> 70, <0.90 -> 54) is a SEPARATE
    field, `run.aqs_token.s1_veto_applied`, produced only in Token mode, which
    this layer does not read — so session failure is not observable at campaign
    level at all. D-159 corrects the inverted causal reading D-154 shipped.
    """
    aqs_obj = run_obj(rec).get("aqs") or {}
    return bool(aqs_obj.get("veto_applied")), bool(aqs_obj.get("low_confidence"))


def run_aqs(rec):
    """run.aqs.score with legacy fallbacks (top-level aqs / aqs_result.score)."""
    aqs_obj = run_obj(rec).get("aqs") or {}
    v = fnum(aqs_obj.get("score"))
    if v is None:
        v = fnum(rec.get("aqs")) or fnum((rec.get("aqs_result") or {}).get("score"))
    return v


def run_started_ms(rec):
    return fnum(run_obj(rec).get("started_at_epoch_ms"))


# Records produced by scripts/synth_campaign.py carry BOTH of these markers.
# Either one alone is enough to detect them: a re-labelled corpus
# (annotate_campaign) keeps the additive block, and a corpus stripped of the
# block still carries the campaign_id prefix. Fabricated numbers must never be
# able to launder themselves into looking like field measurements.
SYNTHETIC_CAMPAIGN_PREFIX = "SYNTH-"


def is_synthetic(rec):
    """True when this record is generated, not measured (see synth_campaign.py)."""
    if isinstance(rec.get("synthetic"), dict):
        return True
    cid = (run_obj(rec).get("campaign") or {}).get("campaign_id")
    return isinstance(cid, str) and cid.startswith(SYNTHETIC_CAMPAIGN_PREFIX)


def count_synthetic(records):
    return sum(1 for r in records if is_synthetic(r))


def run_sub_scores(rec):
    """run.aqs.sub_scores: {KPI-dimension id -> 0-100 sub-score}, numbers only.

    Empty {} for a not-computable run (R-10: the map is empty, never 0-filled),
    so callers treat 'no sub-scores' as a coverage gap, not a zero score.
    """
    subs = (run_obj(rec).get("aqs") or {}).get("sub_scores") or {}
    if not isinstance(subs, dict):
        return {}
    return {k: v for k, v in subs.items() if fnum(v) is not None}


def iter_scenarios(rec):
    return rec.get("scenarios") or []


def scenario_validity(scn):
    """Normalized lower-case validity (schema enum is upper-case, real records
    have been seen lower-case — normalize so both compare equal)."""
    v = scn.get("validity")
    return v.lower() if isinstance(v, str) else "unknown"


def scenario_order_index(scn):
    """scenarios[].order_index — execution POSITION within the run (0-based).

    Captured by the contract as 拉丁方 counterbalancing evidence; order_effect.py
    consumes it to check the counterbalancing actually cancelled position bias.
    Returns None when absent/non-integer (bools excluded), never a guessed 0.
    """
    v = scn.get("order_index")
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def scenario_profile_version(scn):
    """scenarios[].profile_version — the measurement DEFINITION version.

    Two versions of the same profile_id are NOT the same measurement (D-32 keeps
    s3@0.3.0 and s3@0.2.0 in separate groups). Pooling them into one median
    averages incomparable things, so callers flag a cell that mixes versions.
    """
    v = scn.get("profile_version")
    return str(v) if v is not None and str(v) != "" else None


def histogram_edges(scn):
    """scenarios[].itl_histogram.edges_ms as a hashable signature, or None.

    Counts binned on DIFFERENT edges are not summable (R-27 bucket-version
    contract) — combining them is arithmetically wrong, not merely imprecise.
    """
    hist = scn.get("itl_histogram") or {}
    edges = hist.get("edges_ms")
    return tuple(edges) if isinstance(edges, list) and edges else None


# Access medium, shared by the transport section and the attribution guard:
# 铁律 3 also requires the SAME ACCESS across tiers, so both sides must agree
# on what counts as wifi vs cellular (D-157).
TRANSPORT_EXPLICIT = frozenset(("wifi", "cellular"))


def _transport_medium(s):
    """Normalize one transport string to wifi|cellular|None. The real producer
    writes the RESOLVED medium in a compound form — e.g. `auto(cellular)`
    (observed on real corpus, D-110) — so the parenthesized part wins."""
    if not isinstance(s, str) or not s:
        return None
    s = s.lower()
    if s in TRANSPORT_EXPLICIT:
        return s
    m = re.fullmatch(r"\w+\((wifi|cellular)\)", s)
    return m.group(1) if m else None


def resolve_transport(rec):
    """One transport label per run: explicit setting, else observed consensus."""
    t = _transport_medium((rec.get("run") or {}).get("transport"))
    if t:
        return t
    seen = set()
    for scn in iter_scenarios(rec):
        ns = scn.get("network_snapshot")
        if isinstance(ns, dict):
            o = _transport_medium(ns.get("transport"))
            if o:
                seen.add(o)
    if not seen:
        return "unknown"
    return seen.pop() if len(seen) == 1 else "mixed"


def homogeneity_acc():
    """Fresh per-cell comparability accumulator (see note_homogeneity/mixed_flags)."""
    return {"profile_versions": set(), "histogram_edges": set(),
            "modes": set(), "profile_sources": set(), "campaigns": set(),
            "transports": set()}


def note_run_homogeneity(acc, rec):
    """Record one run's comparability signatures: run.mode (quick vs forensic =
    different repeat rigor) and run.profile_source (server vs assets_fallback =
    different profile provenance). Pooling across either mixes non-comparable
    measurements — same error class the scenario-level signatures guard."""
    run = rec.get("run") or {}
    for field, dst in (("mode", "modes"), ("profile_source", "profile_sources")):
        v = run.get(field)
        if isinstance(v, str) and v:
            acc[dst].add(v)
    cid = (run.get("campaign") or {}).get("campaign_id")
    if isinstance(cid, str) and cid:
        acc["campaigns"].add(cid)
    # 铁律 3 requires the same ACCESS across tiers. metro over venue wifi and
    # core over the SIM makes the "core increment" a wifi-vs-cellular gap
    # wearing a backbone label — and the field is right there (D-157).
    acc["transports"].add(resolve_transport(rec))


def mixed_campaigns(acc):
    """Campaign ids pooled into one cell — empty when the cell is one campaign.

    Separate from mixed_run_flags so its 2-tuple contract stays intact. Campaign
    is the most consequential incomparability of all: a cell pooling a baseline
    round with an optimisation round shows a median that is NEITHER (D-135).
    """
    ids = sorted((acc or {}).get("campaigns") or [])
    return ids if len(ids) > 1 else []


def mixed_run_flags(acc):
    """(mixed_modes:list, mixed_profile_sources:list) — empty when homogeneous."""
    acc = acc or {}
    modes = sorted(acc.get("modes") or [])
    sources = sorted(acc.get("profile_sources") or [])
    return (modes if len(modes) > 1 else []), (sources if len(sources) > 1 else [])


def mixed_transports(acc):
    """Access media pooled into one cell — empty when homogeneous."""
    ts = sorted((acc or {}).get("transports") or [])
    return ts if len(ts) > 1 else []


def note_homogeneity(acc, scn):
    """Record one scenario's comparability signatures into a cell accumulator."""
    pv = scenario_profile_version(scn)
    if pv is not None:
        acc["profile_versions"].add(pv)
    eg = histogram_edges(scn)
    if eg is not None:
        acc["histogram_edges"].add(eg)


def mixed_flags(acc):
    """(mixed_profile_versions:list, mixed_histogram_edges:bool) for a cell.

    Empty list / False when the cell is homogeneous — i.e. safe to pool.
    """
    acc = acc or {}
    pvs = sorted(acc.get("profile_versions") or [])
    return (pvs if len(pvs) > 1 else []), len(acc.get("histogram_edges") or []) > 1


def scenario_buffering(scn):
    """scenarios[].buffering forensic block (batching annotation), or {} if absent.

    R-05: this is annotation / forensic evidence ONLY — the score/validity are never
    re-judged from it. Callers must label any rollup accordingly. An all-null block
    means 'not detected' (a coverage fact), not 'no batching = 0'.
    """
    b = scn.get("buffering")
    return b if isinstance(b, dict) else {}


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


def _label(v):
    """Hand-typed label -> stripped string, or the explicit unlabeled bucket."""
    return v.strip() if isinstance(v, str) and v.strip() else "unlabeled"


def _label_key(v):
    """Normalised form used ONLY to spot labels that are probably the same one
    typed differently: NFKC (full-width digits fold to ASCII), case-folded,
    internal whitespace collapsed. Never used as a grouping key — merging on it
    would be a judgement the tool is not entitled to make."""
    return " ".join(unicodedata.normalize("NFKC", str(v)).casefold().split())


def label_collisions(records, fields=("point_id", "campaign_id", "carrier", "time_band")):
    """{field: {normalised: [variants]}} for labels that look like the same one.

    A typo that survives stripping — `SZ-CBD-01` vs `sz-cbd-01`, or a full-width
    digit — silently splits a cell in two, and the report cannot show the
    difference because the rendered strings look alike. Reported, not merged.
    """
    seen = {f: {} for f in fields}
    for rec in records:
        labels = campaign_labels(rec)
        for f in fields:
            v = labels.get(f)
            if v is None:
                continue
            seen[f].setdefault(_label_key(v), set()).add(v)
    return {f: {k: sorted(vs) for k, vs in groups.items() if len(vs) > 1}
            for f, groups in seen.items()
            if any(len(vs) > 1 for vs in groups.values())}


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
        # Surrounding whitespace in a hand-typed label has no legitimate meaning
        # and is invisible in every rendering, yet it splits one point into two
        # cells with half the samples each, both flagged low_conf, while the
        # coverage matrix reports the planned cell missing (D-149). Stripped
        # here, like time_band already was. Differences that COULD be meaningful
        # (case, full-width digits) are reported by label_collisions instead of
        # being merged behind the operator's back.
        "campaign_id": _label(c.get("campaign_id")),
        "tier": tier,
        "point_id": _label(c.get("point_id")),
        "carrier": carrier,
        "time_band": time_band.strip().lower() if isinstance(time_band, str) and time_band.strip()
        else "unknown",
    }


# ---------------------------------------------------------------- stats

def _finite(vals):
    """Drop None and non-finite values. NaN is not a measurement, and unlike a
    merely wrong number it destroys its neighbours: it poisons the sort, so one
    NaN makes the median of every other value NaN too. Every aggregate below
    filters through here so no path can smuggle one in (D-148)."""
    return [v for v in vals
            if v is not None and not (isinstance(v, float) and not math.isfinite(v))]


def median(vals):
    vals = _finite(vals)
    return statistics.median(vals) if vals else None


def stdev(vals):
    """Sample standard deviation, or None below two samples (never 0 as a
    stand-in for 'spread unknown')."""
    vals = _finite(vals)
    return statistics.stdev(vals) if len(vals) > 1 else None


def mad(vals):
    """Median absolute deviation — spread that a few outliers cannot inflate,
    which is the point when the outliers are what you are looking for. None
    below two samples (never 0 as a stand-in for 'spread unknown'); a genuine 0
    is returned as 0 and callers must decide what a zero-spread basis means."""
    xs = _finite(vals)
    if len(xs) < 2:
        return None
    m = statistics.median(xs)
    return statistics.median([abs(x - m) for x in xs])


# MAD*1.4826 estimates sigma for a normal distribution.
MAD_TO_SIGMA = 1.4826


# Normal-approximation factor for the standard error of a median. Latency is
# right-skewed, so everything derived from it is an ORDER-OF-MAGNITUDE guide,
# not a significance test — every renderer that shows a derived number says so.
# It lives here because the reading side (D-144 noise scale) and the planning
# side (how many repeats to run) must never disagree about the constant.
MEDIAN_SE_FACTOR = 1.253


def median_se(sd, n):
    """Standard error of the median, or None when spread or n is unknown."""
    if sd is None or not n:
        return None
    return MEDIAN_SE_FACTOR * sd / (n ** 0.5)


def min_detectable_effect(sd, n):
    """Smallest difference between two same-sized cells that would clear the
    noise scale at this spread — i.e. what the sample actually resolves.
    None when spread is unknown (never 0, which would read as 'resolves
    everything')."""
    se = median_se(sd, n)
    return se * math.sqrt(2.0) if se is not None else None


def required_n(sd, effect):
    """Repeats per side needed before a difference of `effect` clears the noise
    scale. None when spread is unknown or the target effect is not positive."""
    if sd is None or effect is None or effect <= 0:
        return None
    return int(math.ceil(2.0 * (MEDIAN_SE_FACTOR * sd / effect) ** 2))


def mean(vals):
    vals = _finite(vals)
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


def md_cell(v):
    """Make any value safe to place inside a markdown table cell.

    Labels are human-typed (point_id comes from an operator — via --set today,
    a UI later). A literal '|' or newline in one splits the row into extra
    columns and the table renders as garbage — and because it is the LABEL
    column, every table in the report breaks at once (D-128).

    Escapes rather than rejects: if a point really is named "SZ|CBD", the report
    must show that, not drop it or crash.
    """
    if v is None:
        return "—"
    return str(v).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def fmt_num(v, digits=1):
    if v is None:
        return "—"
    s = f"{v:.{digits}f}"
    return s.rstrip("0").rstrip(".") if "." in s else s
