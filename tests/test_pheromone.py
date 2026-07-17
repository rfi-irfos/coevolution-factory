"""Tests for pheromone / mycelium value-prop validation (Simeon Q&A #7).

Doctrine under test:
  * track_pheromone() leaves trails (partner/ecocentric/recurrence strong,
    hard_sell anti-trail). Persists in kpi.yaml.
  * vp_strength() = trail sum; high = validated, low = stale.
  * mycelium_share() = decentral reading of collective trail strength.
"""
import sys, os, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import kpi as K


def _tmp():
    d = "/tmp/kpitest_" + str(os.getpid()) + "_ph"
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return d


def test_pheromone_partner_strong():
    base = _tmp()
    K.track_pheromone("gdpr-guard", "partner", base=base)
    K.track_pheromone("gdpr-guard", "ecocentric_pass", base=base)
    K.track_pheromone("gdpr-guard", "recurrence", base=base)
    strength = K.vp_strength("gdpr-guard", base=base)
    assert strength > 1.0, strength  # 1.0 + 0.5 + 0.3


def test_hard_sell_evaporates():
    base = _tmp()
    K.track_pheromone("gdpr-guard", "partner", base=base)  # +1.0
    K.track_pheromone("gdpr-guard", "hard_sell", base=base)  # -1.0
    strength = K.vp_strength("gdpr-guard", base=base)
    assert strength == 0.0, strength  # trail evaporated


def test_mycelium_share_decentral():
    base = _tmp()
    K.track_pheromone("gdpr-guard", "partner", base=base)
    K.track_pheromone("ai-act-guard", "recurrence", base=base)
    shared = K.mycelium_share(["gdpr-guard", "ai-act-guard"], base=base)
    assert shared["gdpr-guard"] == 1.0
    assert shared["ai-act-guard"] == 0.3
