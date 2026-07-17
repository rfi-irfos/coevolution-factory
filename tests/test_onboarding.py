"""Tests for onboarding / foraging bootstrap (Simeon Q&A #14).

Doctrine under test:
  * onboard_firm(): 3-phase bootstrap (inherit DNA -> mentor adopts -> forage).
  * A firm is 'larva' until it earns its first real partner pheromone.
  * mark_foraged(): self-earned trail (not inherited) promotes larva->autonomous.
"""
import sys, os, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import kpi as K


def _tmp():
    d = "/tmp/kpitest_" + str(os.getpid()) + "_onboard"
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return d


def test_onboard_three_phases():
    base = _tmp()
    K.track_pheromone("gdpr-guard", "partner", base=base)  # mentor strength
    rec = K.onboard_firm("new-daughter", ["gdpr-guard"], "gdpr-guard", base=base)
    assert rec["phases"] == ["inherit_dna", "mentor_adoption", "foraging"]
    assert rec["state"] == "larva"  # not autonomous yet, must forage


def test_larva_until_foraged():
    base = _tmp()
    K.track_pheromone("gdpr-guard", "partner", base=base)
    K.onboard_firm("new-daughter", ["gdpr-guard"], "gdpr-guard", base=base)
    # before foraging, still larva
    assert K.load_kpi("new-daughter", base=base).get("state") != "autonomous"
    # earns first real partner pheromone via foraging
    K.track_pheromone("new-daughter", "partner", base=base)
    state = K.mark_foraged("new-daughter", base=base)
    assert state == "autonomous"


def test_foraging_is_self_earned_not_inherited():
    base = _tmp()
    K.track_pheromone("gdpr-guard", "partner", base=base)  # mentor 1.0
    K.onboard_firm("new-daughter", ["gdpr-guard"], "gdpr-guard", base=base)
    # inherited + mentor dilution, but NOT 'autonomous' until it forages itself
    k = K.load_kpi("new-daughter", base=base)
    assert k["onboarding"]["state"] == "larva"
    assert k["onboarding"]["mentor"] == "gdpr-guard"
