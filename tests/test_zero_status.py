"""Tests for 0-status-as-default (Simeon Q&A #6).

Doctrine under test:
  * ZERO_STATUS_IS_DEFAULT = True: tend (0) is the safe resting state.
  * resolve_signal() never raises; undefined/ambiguous -> tend.
  * "Doing nothing is often faster and safer than doing something."
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import governance as G


def test_zero_status_is_default_flag():
    assert G.ZERO_STATUS_IS_DEFAULT is True
    assert G.DEFAULT_STATE == "tend"
    assert G.TEND_ON_UNDEFINED is True


def test_resolve_none_to_tend():
    assert G.resolve_signal(None) == "tend"


def test_resolve_zero_to_tend():
    # 0 (the ternary zero) -> hold, not an error
    assert G.resolve_signal(0) == "tend"


def test_resolve_trits():
    assert G.resolve_signal(1) == "affirm"
    assert G.resolve_signal(-1) == "reject"
    assert G.resolve_signal(0.5) == "affirm"
    assert G.resolve_signal(-0.3) == "reject"


def test_resolve_ambiguous_never_crashes():
    # non-numeric / unclear -> tend, no exception
    assert G.resolve_signal("unclear") == "tend"
    assert G.resolve_signal(object()) == "tend"
    assert G.resolve_signal(float("nan")) == "tend"  # nan -> not >0, not <0 -> tend
