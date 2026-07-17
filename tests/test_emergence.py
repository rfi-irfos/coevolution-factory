"""Tests for emergence + input/output/hallucination distinction (Q&A #10).

Doctrine under test:
  * EMERGENCE_ALLOWED = True (full gas; ideas/intuition are the juice).
  * classify_signal(): input=raw, output=computed(grounded?),
    emergence=broadcastable, ungrounded output=hallucination (flagged).
  * SOFT_COMPETITION = True (one north-star, shared genetics -> symbiotic).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import governance as G


def test_emergence_allowed_full_gas():
    assert G.EMERGENCE_ALLOWED is True
    assert G.SOFT_COMPETITION is True
    assert G.NORTH_STAR == "2040-09-08"


def test_classify_input():
    ch, ok, note = G.classify_signal("input")
    assert ch == "input" and ok is False


def test_classify_output_grounded():
    ch, ok, note = G.classify_signal("output", grounded=True)
    assert ch == "output" and ok is True


def test_classify_output_ungrounded_is_hallucination():
    ch, ok, note = G.classify_signal("output", grounded=False)
    assert ch == "hallucination"
    assert ok is False
    assert "never broadcast" in note


def test_classify_emergence_broadcastable():
    ch, ok, note = G.classify_signal("emergence")
    assert ch == "emergence"
    assert ok is True  # the juice -> broadcast to mycelium
    assert "broadcast" in note
