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
                 time_band="busy", profile="s1_chat", campaign_id="base"):
    """n records tagged with `tier`, each carrying one scenario with kpi_key=value."""
    campaign = {"campaign_id": campaign_id, "tier": tier, "point_id": point,
                "carrier": carrier, "time_band": time_band}
    return [make_record(campaign=campaign, scenarios=[(profile, {kpi_key: value})])
            for _ in range(n)]


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
