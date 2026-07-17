"""Tests for succession: a firm never dies, it disperses to the wind (Q&A #12).

Doctrine under test:
  * NO_FIRM_DEATH = True: a firm goes to seed, never deleted.
  * disperse_to_wind(): firm -> 'dispersed', broadcasts KPIs/pheromones as
    nourishment (never removed from disk).
  * absorb_nourishment(): another firm grows stronger from the nourishment.
"""
import sys, os, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import kpi as K


def _tmp():
    d = "/tmp/kpitest_" + str(os.getpid()) + "_succ"
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return d


def test_no_firm_death_flag():
    assert K.NO_FIRM_DEATH is True
    assert K.DISPERSED_STATE == "dispersed"


def test_disperse_to_wind_keeps_file():
    base = _tmp()
    K.track_pheromone("gdpr-guard", "partner", base=base)  # trail 1.0
    food = K.disperse_to_wind("gdpr-guard", base=base)
    assert food["slug"] == "gdpr-guard"
    # firm is NOT deleted — still on disk, just 'dispersed'
    k = K.load_kpi("gdpr-guard", base=base)
    assert k["state"] == "dispersed"
    assert os.path.exists(K.kpi_path("gdpr-guard", base=base))


def test_absorb_nourishment_grows_other():
    base = _tmp()
    K.track_pheromone("gdpr-guard", "partner", base=base)  # 1.0
    food = K.disperse_to_wind("gdpr-guard", base=base)
    # another firm absorbs -> its trail strengthens
    before = K.vp_strength("ai-act-guard", base=base)
    after = K.absorb_nourishment("ai-act-guard", food, base=base)
    assert after > before
    assert after == 1.0  # absorbed the 1.0 partner pheromone
