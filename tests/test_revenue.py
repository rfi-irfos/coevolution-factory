"""Tests for revenue tracking + Lighthouse cashflow (Simeon Q&A #8).

Doctrine under test:
  * Firms track their OWN revenue (decentral, in kpi.yaml).
  * Only partner/ecocentric sources count; hard-sell/churn banned.
  * lighthouse_cashflow() aggregates into the OS Finance tab; highest earner
    by 2040 Jubilaeum is the party-payer (transparent).
"""
import sys, os, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import kpi as K


def _tmp():
    d = "/tmp/kpitest_" + str(os.getpid()) + "_rev"
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return d


def test_revenue_partner_counts():
    base = _tmp()
    total = K.track_revenue("gdpr-guard", 25.0, "partner", base=base)
    assert total == 25.0
    assert K.vp_revenue("gdpr-guard", base=base) == 25.0


def test_revenue_hard_sell_banned():
    base = _tmp()
    total = K.track_revenue("gdpr-guard", 999.0, "hard_sell", base=base)
    # banned -> not counted
    assert total == 0.0
    assert K.vp_revenue("gdpr-guard", base=base) == 0.0
    k = K.load_kpi("gdpr-guard", base=base)
    assert k.get("rejected_revenue"), "should record rejection marker"


def test_lighthouse_cashflow_party_payer():
    base = _tmp()
    K.track_revenue("gdpr-guard", 50.0, "partner", base=base)
    K.track_revenue("ai-act-guard", 80.0, "recurring", base=base)
    cf = K.lighthouse_cashflow(["gdpr-guard", "ai-act-guard"], base=base)
    assert cf["cashflow"] == 130.0
    assert cf["party_payer"] == "ai-act-guard"  # highest earner pays party
    assert cf["lines"]["ai-act-guard"] == 80.0
