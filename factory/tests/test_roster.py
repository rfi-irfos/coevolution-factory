import os
import sys

# Ensure the factory package root is importable when pytest runs from factory/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import catalog


def test_derive_roster_has_departments():
    roster = catalog.derive_roster(["legal-privacy", "risk-gdpr", "sec-appsec"])
    assert "departments" in roster
    assert len(roster["departments"]) >= 1


def test_derive_roster_every_member_has_role():
    roster = catalog.derive_roster(["a", "b", "c"])
    people = []
    for d in roster["departments"]:
        people.append(d["lead"])
        people += d["experts"]
    assert all(p.get("role") in ("lead", "expert") for p in people)


def test_every_center_has_roster_with_lead():
    for slug, m in catalog.CENTERS_META.items():
        r = m["roster"]
        assert r["departments"], slug
        assert all(d["lead"]["role"] == "lead" for d in r["departments"]), slug
