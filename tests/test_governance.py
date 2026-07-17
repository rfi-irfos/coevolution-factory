"""Tests for governance defaults (Simeon's hard-coded firm constitution).

Doctrine under test:
  * PING_INTERVAL_HOURS = 12 (firms are agents, regular pulse).
  * MIN_LEGAL_PATHS = 3 (never A/B, always A/B/C).
  * EXPERIMENT_WINDOW_DAYS = 7 (A/B/C, never only A/B).
  * ORIENTATION = ecocentric. DEFAULT_STATE = tend.
  * lunar_phase_name() is deterministic (no network) + maps to plan_phase.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import governance as G
from datetime import datetime, timezone, timedelta


def test_constants():
    assert G.PING_INTERVAL_HOURS == 12
    assert G.MIN_LEGAL_PATHS == 3
    assert G.EXPERIMENT_WINDOW_DAYS == 7
    assert G.ORIENTATION == "ecocentric"
    assert G.DEFAULT_STATE == "tend"
    assert G.DEFAULTS["min_legal_paths"] == 3


def test_lunar_phase_deterministic():
    # reference new moon -> 'new'
    nm = datetime(2026, 7, 14, 10, 43, 0, tzinfo=timezone.utc)
    name, days, illum = G.lunar_phase_name(nm)
    assert name == "new", name
    assert days == 0.0
    assert illum < 0.05  # new moon ~ dark
    # ~14.77 days later -> full
    full = nm + timedelta(days=G.LUNAR_PERIOD_DAYS / 2)
    name2, _, illum2 = G.lunar_phase_name(full)
    assert name2 == "full", name2
    assert illum2 > 0.95  # full moon ~ bright


def test_plan_phase_mapping():
    nm = datetime(2026, 7, 14, 10, 43, 0, tzinfo=timezone.utc)
    assert G.plan_phase(nm) == "set_new_plans"
    full = nm + timedelta(days=G.LUNAR_PERIOD_DAYS / 2)
    assert G.plan_phase(full) == "peak_validation"
    # first quarter ~ 7.38 days after new
    fq = nm + timedelta(days=G.LUNAR_PERIOD_DAYS / 4)
    assert G.plan_phase(fq) == "launch"


def test_evaluate_ecocentric_veto_self_serving():
    # serves only the human, harms the wider whole -> HARD VETO
    verdict, reason = G.evaluate_ecocentric(1, -1)
    assert verdict == "veto", reason
    assert "only the requester" in reason


def test_evaluate_ecocentric_hold_unclear():
    # unclear whether it serves the whole -> hold in tend (Wall-E mode)
    verdict, _ = G.evaluate_ecocentric(1, 0)
    assert verdict == "hold"


def test_evaluate_ecocentric_pass_serves_whole():
    # serves human + eco -> pass (not only self)
    verdict, _ = G.evaluate_ecocentric(1, 1)
    assert verdict == "pass"


def test_evaluate_ecocentric_veto_nobody():
    verdict, _ = G.evaluate_ecocentric(-1, -1)
    assert verdict == "veto"


def test_score_lead_partner_compounds():
    # brings referrals -> 'partner' tier, high score
    score, tier = G.score_lead(recurrence=5, referral=2, fit=0.9)
    assert tier == "partner"
    assert score > 0.8


def test_score_lead_rejects_hard_sell():
    # we never hard-sell; a pushed lead is disqualified
    score, tier = G.score_lead(recurrence=10, referral=10, fit=1.0,
                               hard_sell_attempt=True)
    assert tier == "rejected_hard_sell"
    assert score == 0.0


def test_score_lead_no_fit_cold():
    score, tier = G.score_lead(recurrence=0, referral=0, fit=0.0)
    assert tier == "no_fit"
    assert score == 0.0


def test_score_lead_recurring_tier():
    score, tier = G.score_lead(recurrence=4, referral=0, fit=0.8)
    assert tier == "recurring"
