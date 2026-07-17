"""Tests for daughter-spawn constitution gate (Simeon Q&A #5).

Doctrine under test:
  * A daughter needs >=3 core primitives.
  * Must be legal (hard ban on forbidden domains).
  * Must solve a real physical-world problem (ecocentric).
  * Must be crisis-resistant.
  * No near-duplicate of an existing firm (no conflict of interest) — judged
    by core-primitive overlap, not mandate wording.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import governance as G

GOOD = {
    "name": "SupplyChainResilience Center", "slug": "supply-resilience",
    "mandate": "standing SRE panel that finds single points of failure",
    "core_primitives": ["resilience", "risk", "ops"],
    "legal": True, "solves_real_problem": True, "crisis_resistant": True,
}
EXISTING_SLUGS = ["gdpr-guard", "ai-act-guard"]
EXISTING_PRIMITIVES = [["privacy", "risk", "law"], ["ai", "safety", "law"]]


def test_spawn_ok_when_all_criteria_met():
    ok, why = G.should_spawn_daughter(GOOD, EXISTING_SLUGS, EXISTING_PRIMITIVES)
    assert ok, why


def test_spawn_rejects_few_primitives():
    p = dict(GOOD, core_primitives=["resilience", "risk"])
    ok, why = G.should_spawn_daughter(p, EXISTING_SLUGS, EXISTING_PRIMITIVES)
    assert not ok and "core primitives" in why


def test_spawn_rejects_illegal():
    p = dict(GOOD, legal=False)
    ok, why = G.should_spawn_daughter(p, EXISTING_SLUGS, EXISTING_PRIMITIVES)
    assert not ok and "not legal" in why


def test_spawn_rejects_forbidden_domain():
    p = dict(GOOD, name="Weapons Trade Desk",
             mandate="broker weapons deals")
    ok, why = G.should_spawn_daughter(p, EXISTING_SLUGS, EXISTING_PRIMITIVES)
    assert not ok and "forbidden domain" in why


def test_spawn_rejects_duplicate_slug():
    p = dict(GOOD, slug="gdpr-guard")
    ok, why = G.should_spawn_daughter(p, EXISTING_SLUGS, EXISTING_PRIMITIVES)
    assert not ok and "already exists" in why


def test_spawn_rejects_near_duplicate_primitives():
    # shares 2/3 primitives with an existing firm -> too similar
    p = dict(GOOD, slug="new-thing", core_primitives=["privacy", "risk", "ops"])
    ok, why = G.should_spawn_daughter(p, EXISTING_SLUGS, EXISTING_PRIMITIVES)
    assert not ok and "too similar" in why
