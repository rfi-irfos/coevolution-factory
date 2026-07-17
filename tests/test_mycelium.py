"""Tests for active mycelium collaboration (Simeon Q&A #9).

Doctrine under test:
  * broadcast(): a firm broadcasts its trail (vp_strength, problems, mandate).
  * broadcast_gap(): a firm pools an uncovered problem into the mycelium.
  * mycelium_index(): decentral read of all broadcasts (living network map).
  * mycelium_gaps(): collective read of pooled gaps (no central allocator).
"""
import sys, os, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import kpi as K


def _tmp():
    d = "/tmp/kpitest_" + str(os.getpid()) + "_myc"
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return d


def test_broadcast_writes_trail():
    base = _tmp()
    K.track_pheromone("gdpr-guard", "partner", base=base)  # vp_strength 1.0
    rec = K.broadcast("gdpr-guard", base=base)
    assert rec["vp_strength"] == 1.0
    assert "slug" in rec and rec["slug"] == "gdpr-guard"


def test_broadcast_gap_pools():
    base = _tmp()
    gap = K.broadcast_gap("gdpr-guard", "uncovered: AI training data lineage", base=base)
    assert gap["from"] == "gdpr-guard"
    assert "AI training data lineage" in gap["gap"]


def test_mycelium_index_decentral():
    base = _tmp()
    K.track_pheromone("gdpr-guard", "partner", base=base)
    K.track_pheromone("ai-act-guard", "recurrence", base=base)
    K.broadcast("gdpr-guard", base=base)
    K.broadcast("ai-act-guard", base=base)
    idx = K.mycelium_index(["gdpr-guard", "ai-act-guard"], base=base)
    assert set(idx.keys()) == {"gdpr-guard", "ai-act-guard"}
    assert idx["gdpr-guard"]["vp_strength"] == 1.0


def test_mycelium_gaps_collective():
    base = _tmp()
    K.broadcast_gap("gdpr-guard", "gap A", base=base)
    K.broadcast_gap("ai-act-guard", "gap B", base=base)
    gaps = K.mycelium_gaps(["gdpr-guard", "ai-act-guard"], base=base)
    assert len(gaps) == 2
