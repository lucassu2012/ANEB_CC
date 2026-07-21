# -*- coding: utf-8 -*-
"""Synthetic result-record factory for campaign-analysis reflex tests.

Builds in-memory records matching spec/schemas/result-run.schema.json shape
(only the fields the analysis layer reads). No real data files, no device, no
network — pure fixtures so the golden tests encode the methodology insights.
"""


_SEQ = [0]  # monotonic fixture counter -> unique run_id per record


def make_record(*, campaign=None, aqs=None, scenarios=(), run_id=None):
    """scenarios: iterable of (profile_id, {kpi_key: value, ...}).

    run_id defaults to a UNIQUE per-record id (real runs never share one, and
    load_records now de-duplicates by it). Pass run_id explicitly to build a
    deliberate duplicate/conflict fixture.
    """
    _SEQ[0] += 1
    rid = run_id if run_id is not None else "test-%04d" % _SEQ[0]
    run = {
        "run_id": rid, "started_at_epoch_ms": 1783944000000, "mode": "quick",
        "scenario_order": "", "transport": "auto", "profile_source": "server",
        "app_version_name": "t", "app_version_code": 1, "guard_metadata": None,
        "status": "completed",
        "aqs": {"score": aqs, "low_confidence": False, "veto_applied": False,
                "not_computable_reason": None, "input_mapping": "", "sub_scores": {}},
    }
    if campaign is not None:
        run["campaign"] = campaign
    scns = []
    for pid, kpi in scenarios:
        scns.append({
            "profile_id": pid, "profile_version": "0", "repeat_index": 0, "order_index": 0,
            "validity": "valid", "invalid_reasons": "", "kpi": kpi, "clock": {},
            "network_snapshot": {}, "parse": {}, "buffering": {}, "itl_histogram": {},
        })
    return {
        "claim_scope": "application_end_to_end_to_probe_node", "kpi_set": "t",
        "aqs_version": "t", "profile_versions": "t", "schema_version": "1.0",
        "run": run, "scenarios": scns,
    }


def tier_records(tier, kpi_key, value, n, *, point="P1", carrier="cmcc",
                 time_band="busy", profile="s1_chat", campaign_id="base",
                 profile_version=None, edges_ms=None):
    """n records tagged with `tier`, each carrying one scenario with kpi_key=value.

    profile_version / edges_ms override the scenario's comparability signatures
    so tests can build a cell that pools INCOMPARABLE measurements (D-32 / R-27).
    """
    campaign = {"campaign_id": campaign_id, "tier": tier, "point_id": point,
                "carrier": carrier, "time_band": time_band}
    out = []
    for _ in range(n):
        rec = make_record(campaign=campaign, scenarios=[(profile, {kpi_key: value})])
        if profile_version is not None:
            rec["scenarios"][0]["profile_version"] = profile_version
        if edges_ms is not None:
            rec["scenarios"][0]["itl_histogram"] = {"edges_ms": list(edges_ms),
                                                    "counts": [0] * (len(edges_ms) + 1)}
        out.append(rec)
    return out


def validity_records(n, *, validity="valid", invalid_reasons="", profile="s1_chat",
                     point="P1", carrier="cmcc", time_band="busy", tier="metro",
                     campaign_id="base", kpi=None):
    """n records whose single scenario carries the given validity / invalid_reasons."""
    campaign = {"campaign_id": campaign_id, "tier": tier, "point_id": point,
                "carrier": carrier, "time_band": time_band}
    out = []
    for _ in range(n):
        rec = make_record(campaign=campaign, scenarios=[(profile, dict(kpi or {}))])
        rec["scenarios"][0]["validity"] = validity
        rec["scenarios"][0]["invalid_reasons"] = invalid_reasons
        out.append(rec)
    return out


def order_records(n, *, kpi_key="t1_ttft_ms", value=100, order_index=0,
                  profile="s1_chat", scenario_order="s1_chat,s2_rag", point="P1",
                  carrier="cmcc", time_band="busy", tier="metro", campaign_id="base"):
    """n records whose single scenario ran at execution position `order_index`.

    Used to build a known position-vs-KPI relationship for the order-effect tests.
    """
    campaign = {"campaign_id": campaign_id, "tier": tier, "point_id": point,
                "carrier": carrier, "time_band": time_band}
    out = []
    for _ in range(n):
        rec = make_record(campaign=campaign, scenarios=[(profile, {kpi_key: value})])
        rec["scenarios"][0]["order_index"] = order_index
        rec["run"]["scenario_order"] = scenario_order
        out.append(rec)
    return out


def aqs_records(aqs, n, *, point="P1", carrier="cmcc", time_band="busy",
                campaign_id="base", tier="metro"):
    """n records with run.aqs.score=aqs and the given campaign labels (no scenarios)."""
    campaign = {"campaign_id": campaign_id, "tier": tier, "point_id": point,
                "carrier": carrier, "time_band": time_band}
    return [make_record(campaign=campaign, aqs=aqs, scenarios=[]) for _ in range(n)]


def kpi_scenario_records(n, *, kpi=None, point="P1", carrier="cmcc", time_band="busy",
                         tier="metro", campaign_id="base", aqs=None, profile="s1_chat"):
    """n records each with one scenario carrying the given kpi dict (value + *_grade)."""
    campaign = {"campaign_id": campaign_id, "tier": tier, "point_id": point,
                "carrier": carrier, "time_band": time_band}
    return [make_record(campaign=campaign, aqs=aqs, scenarios=[(profile, dict(kpi or {}))])
            for _ in range(n)]
