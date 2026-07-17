"""Tests for temporal cognition (Simeon's mandatory time-anchoring doctrine).

Doctrine under test:
  * stamp() emits canonical 'Fri/2026-07-17T15:09:11Z/1784300951' format.
  * ts_id() builds '{epoch}/{hash}' primary keys.
  * cognition() returns past/present/future anchors.
  * north_star() is fixed at 2040-09-08.
  * years_to_north_star() is positive (future-facing motivation).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import temporal as T


def test_stamp_format():
    s = T.stamp(1784300951)
    assert s == "Fri/2026-07-17T15:09:11Z/1784300951", s
    # parseable back
    wd, iso, ep = T.parse(s)
    assert wd == "Fri" and iso == "2026-07-17T15:09:11Z" and ep == 1784300951


def test_ts_id_schema():
    rid = T.ts_id(1784300951, "gdpr-guard")
    epoch, h = rid.split("/")
    assert epoch == "1784300951"
    assert len(h) == 8  # short_hash [:8]
    # deterministic: same input -> same id
    assert rid == T.ts_id(1784300951, "gdpr-guard")


def test_cognition_anchors():
    cog = T.cognition(1784300951)
    assert cog["past_anchor"].endswith("/1784300951")
    assert cog["future_north_star"] == "2040-09-08"
    # present falls back to born when no action yet
    assert cog["present_anchor"].endswith("/1784300951")


def test_north_star_fixed():
    iso, ep = T.north_star()
    assert iso == "2040-09-08"
    assert ep > 1784300951  # future


def test_years_to_north_star_positive():
    y = T.years_to_north_star(1784300951)
    assert y > 0  # we are before 2040
    assert 13.0 < y < 15.0  # ~14 years from 2026


def test_load_state_migration_adds_born_at(tmp_path, monkeypatch):
    import runtime as R
    monkeypatch.setattr(R, "DB", tmp_path / "state.json")
    # seed a center WITHOUT born_at + a usage record WITHOUT ts_id
    s = {"centers": {"gdpr-guard": {"version": 1, "is_daughter": False}},
         "daughter_centers": {}, "usage": [{"center": "gdpr-guard", "ts": 1784300951}]}
    R.DB.write_text(__import__("json").dumps(s))
    loaded = R.load_state()
    reg = loaded["centers"]["gdpr-guard"]
    assert "born_at" in reg, "migration must set born_at"
    assert "cognition" in reg, "migration must set cognition block"
    assert reg["cognition"]["future_north_star"] == "2040-09-08"
    assert loaded["usage"][0]["ts_id"].startswith("1784300951/"), \
        "usage record must get {epoch}/{hash} ts_id"
