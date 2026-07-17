"""Tests for gamification + honeycomb UI helpers (Simeon: gamify the hive).

Doctrine under test:
  * firm_level(): 1 + log2(real impact), min 1 (no vanity, real).
  * jubilee_progress(): 0..1 from birth toward 2040-09-08 north-star.
  * achievements(): real, verifiable badges (first_solve, trail, partner...).
  * hex_css(): honeycomb clip-path (no squares).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ui_gamify as U


def test_firm_level_floor_one():
    assert U.firm_level("x", problems_solved=0, vp_strength=0.0) == 1
    assert U.firm_level("x", problems_solved=3, vp_strength=1.0) >= 2


def test_firm_level_grows_with_impact():
    low = U.firm_level("x", problems_solved=1, vp_strength=0.0)
    high = U.firm_level("x", problems_solved=50, vp_strength=10.0)
    assert high > low


def test_jubilee_progress_range():
    # born now -> progress ~0; born in 2026, north 2040 -> small but >0
    now = int(__import__("datetime").datetime.now(__import__("datetime").timezone.utc).timestamp())
    p = U.jubilee_progress(now)
    assert 0.0 <= p <= 1.0
    # far future birth (after north 2040) -> 1.0 (clamped)
    assert U.jubilee_progress(2300000000) == 1.0


def test_achievements_real_milestones():
    a = U.achievements("x", problems_solved=2, vp_strength=1.5,
                       revenue_eur=50.0, crisis_survived=True)
    names = [b[0] for b in a]
    assert "first_solve" in names
    assert "trail" in names
    assert "first_partner" in names
    assert "crisis_survivor" in names


def test_hex_css_is_honeycomb():
    css = U.hex_css()
    assert "polygon" in css
    assert "50%" in css  # hex center point
