"""Tests for Hive Mind / Queen / genetic inheritance (Simeon Q&A #13).

Doctrine under test:
  * HIVE_MIND = True (no string theory; ant colony model).
  * record_collective_memory(): Queen records dispersed knowledge into the
    hive genome (DNA), cumulative across generations.
  * queen_fly(): returns genetic mix of strongest parents (crossover material).
  * inherit_genetics(): a new daughter inherits diluted mix from top parents.
"""
import sys, os, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import kpi as K


def _tmp():
    d = "/tmp/kpitest_" + str(os.getpid()) + "_hive"
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return d


def test_hive_mind_flag():
    assert K.HIVE_MIND is True
    assert K.QUEEN_STATE == "flying"


def test_collective_memory_cumulative():
    base = _tmp()
    gen1 = K.record_collective_memory({"slug": "gdpr-guard", "pheromones": {"partner": 1.0}}, base=base)
    gen2 = K.record_collective_memory({"slug": "ai-act-guard", "pheromones": {"recurrence": 0.3}}, base=base)
    assert gen2 == 2  # cumulative generations
    gen = K.load_kpi  # genome is separate file
    import yaml
    g = yaml.safe_load(open(K.collective_memory_path(base)))
    assert len(g["dna"]) == 2


def test_queen_fly_ranks_strongest():
    base = _tmp()
    K.track_pheromone("gdpr-guard", "partner", base=base)       # 1.0
    K.track_pheromone("ai-act-guard", "recurrence", base=base)  # 0.3
    mix = K.queen_fly(["gdpr-guard", "ai-act-guard"], base=base)
    assert mix["strongest_parent"] == "gdpr-guard"
    assert mix["queen_state"] == "flying"


def test_inherit_genetics_diluted():
    base = _tmp()
    K.track_pheromone("gdpr-guard", "partner", base=base)  # 1.0
    child = K.inherit_genetics("new-daughter", ["gdpr-guard", "ai-act-guard"], base=base)
    # diluted 0.5 * 1.0 = 0.5 inherited
    assert child == 0.5
