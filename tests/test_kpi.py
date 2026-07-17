"""Tests for per-firm KPI tracking + lunar review cycle (Simeon Q&A #4).

Doctrine under test:
  * track_kpi() writes metrics into a persistent kpi.yaml (self-knowledge).
  * review_at_last_quarter() adjusts based on ecocentric pass-rate + partner.
  * plan_at_new_moon() builds next plans from KPI trend.
  * File persists across calls (not just memory).
"""
import sys, os, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import kpi as K


def _tmp():
    d = "/tmp/kpitest_" + str(os.getpid())
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return d


def test_track_kpi_persists():
    base = _tmp()
    K.track_kpi("gdpr-guard", "partner_score", 0.9, base=base)
    K.track_kpi("gdpr-guard", "ecocentric_pass_rate", 1.0, base=base)
    # reload from disk (not memory)
    k = K.load_kpi("gdpr-guard", base=base)
    assert k["metrics"]["partner_score"] == 0.9
    assert k["metrics"]["ecocentric_pass_rate"] == 1.0
    assert len(k["history"]) == 2


def test_review_last_quarter_adjusts():
    base = _tmp()
    K.track_kpi("gdpr-guard", "ecocentric_pass_rate", 0.3, base=base)
    rec = K.review_at_last_quarter("gdpr-guard", base=base)
    assert rec["adjust"] == "halt_self_serving_actions; re-anchor ecocentric"
    # persisted
    k = K.load_kpi("gdpr-guard", base=base)
    assert any(p.get("phase") == "last_quarter_adjust" for p in k["plans"])


def test_plan_new_moon_builds():
    base = _tmp()
    K.track_kpi("gdpr-guard", "partner_score", 0.7, base=base)
    plan = K.plan_at_new_moon("gdpr-guard", base=base)
    assert plan["phase"] == "new_moon"
    assert plan["orientation"] == "ecocentric"
    assert plan["min_legal_paths"] == 3
