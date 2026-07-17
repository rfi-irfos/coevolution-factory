"""Task 3: per-center CRM / leads populated ONLY from REAL visitor traffic.

A lead is created when a REAL inbound question triggers a panel session or an
inter-center debate. The raw question is NEVER stored — only a SHA-256 hash —
so no PII lands in state. Leads are surfaced read-only in /observatory.

Fully OFFLINE: the engine is neutralised via monkeypatch (call_engine /
engine_synthesize), and the background jobs are invoked directly (no
TestServer / event-loop binding, so this file coexists with test_debate.py
which owns its own module-level loop). We reuse the exact session/debate
ingestion hooks (run_panel_job / run_debate_job) so we exercise the real
lead-creation path, not a reimplementation.

conftest.py freezes FT_STATE_DIR to a temp dir, so state.json is isolated.
"""

import os
import sys
import asyncio
import hashlib
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "factory"))

import runtime as R

# gdpr-guard is a real catalog center (own panel + adjacent centers), so we
# exercise real session + debate ingestion without fake-center scaffolding.
_CENTER = "gdpr-guard"
_TEST_KEY = "ct_gdpr_crm_0123456789abcdef"


def _inject_key():
    R.state.setdefault("keys", {})[_TEST_KEY] = {
        "center": _CENTER, "email": "t@t.co",
        "created": 0, "sessions": 0}


async def _fake_upstream(text, panel):
    return {"responses": []}, 200, None


async def _fake_synth(upstream, panel, url, key):
    return {"posture": "stable", "panel_size": len(panel),
            "disciplines_fired": 0, "disciplines_silent": panel,
            "flags": [], "notes": [], "conflicts": [],
            "flag_count": 0, "note_count": 0}


def _run(coro):
    return asyncio.run(coro)


def test_lead_on_session(monkeypatch):
    """An inbound panel session creates exactly ONE 'session' lead with a
    question_hash and NO raw text stored."""
    _inject_key()
    monkeypatch.setattr(R, "DEMO_MODE", False)
    monkeypatch.setattr(R, "call_engine", _fake_upstream)
    monkeypatch.setattr(R, "engine_synthesize", _fake_synth)

    raw_q = "How do I keep our CRM out of GDPR scope for EU leads?"
    run_id = "run_crm_session"
    panel = R.CENTERS[_CENTER]["panel"]
    R.state.setdefault("jobs", {})[run_id] = {
        "center": _CENTER, "status": "queued", "created": int(time.time()),
        "text": raw_q, "panel": panel, "result": None, "error": None}

    _run(R.run_panel_job(run_id, _CENTER, raw_q, panel,
                         R.CENTERS[_CENTER], R.state["keys"][_TEST_KEY]))

    leads = R.state.get("leads", {}).get(_CENTER, [])
    assert len(leads) == 1, leads
    lead = leads[0]
    assert lead["kind"] == "session"
    assert lead["ref"] == run_id
    assert lead["center"] == _CENTER
    assert lead["outcome"] == "stable"
    # hash present + matches raw question
    expected = hashlib.sha256(raw_q.encode("utf-8")).hexdigest()
    assert lead["question_hash"] == expected
    # NO raw text anywhere in the lead dict
    assert "text" not in lead
    for v in lead.values():
        assert raw_q not in str(v), "raw PII question stored!"


def test_lead_on_debate(monkeypatch):
    """An inbound inter-center debate creates a 'debate' lead (separate from
    any session lead, keyed via its own kind)."""
    _inject_key()
    monkeypatch.setattr(R, "DEMO_MODE", False)
    monkeypatch.setattr(R, "call_engine", _fake_upstream)
    monkeypatch.setattr(R, "engine_synthesize", _fake_synth)

    # emulate debate_session's record seeding, then run the real job
    adjacent = R.CENTER_NETWORK.get(_CENTER, [])
    pooled_panel = R._build_pooled_panel(_CENTER)
    raw_q = "Should we pool our breach-response panel with ai-act-guard?"
    run_id = "debate_crm_1"
    R.state.setdefault("debates", {})[run_id] = {
        "center": _CENTER, "adjacent": adjacent, "pooled_panel": pooled_panel,
        "text": raw_q, "status": "queued", "created": int(time.time()),
        "resolution": None, "error": None}

    _run(R.run_debate_job(run_id, _CENTER, raw_q, pooled_panel, adjacent,
                          R.CENTERS[_CENTER], R.state["keys"][_TEST_KEY],
                          None))

    leads = R.state.get("leads", {}).get(_CENTER, [])
    debate_leads = [l for l in leads if l["kind"] == "debate"]
    assert len(debate_leads) == 1, leads
    lead = debate_leads[0]
    assert lead["ref"] == run_id
    assert lead["center"] == _CENTER
    expected = hashlib.sha256(raw_q.encode("utf-8")).hexdigest()
    assert lead["question_hash"] == expected
    assert "text" not in lead
    for v in lead.values():
        assert raw_q not in str(v), "raw PII question stored!"


def test_no_fabrication(monkeypatch):
    """state['leads'] holds NO raw inbound text and NO made-up contacts:
    every lead dict is whitelisted to the honest schema keys."""
    _inject_key()
    monkeypatch.setattr(R, "DEMO_MODE", False)
    monkeypatch.setattr(R, "call_engine", _fake_upstream)
    monkeypatch.setattr(R, "engine_synthesize", _fake_synth)

    raw_q = "Fabrication probe: a completely made-up client email test@x.io"
    # keys that must NEVER appear in a lead (PII / contact fields)
    forbidden_keys = {"text", "email", "name", "phone", "contact", "customer",
                      "address", "ip", "user", "raw", "question", "query"}

    # one session lead
    run_id = "run_crm_fab"
    panel = R.CENTERS[_CENTER]["panel"]
    R.state.setdefault("jobs", {})[run_id] = {
        "center": _CENTER, "status": "queued", "created": int(time.time()),
        "text": raw_q, "panel": panel, "result": None, "error": None}
    _run(R.run_panel_job(run_id, _CENTER, raw_q, panel,
                         R.CENTERS[_CENTER], R.state["keys"][_TEST_KEY]))

    leads = R.state.get("leads", {}).get(_CENTER, [])
    assert len(leads) >= 1
    for lead in leads:
        # only the honest schema is present
        allowed = {"ts", "kind", "ref", "question_hash", "outcome", "center"}
        assert set(lead.keys()) == allowed, \
            f"unexpected lead keys: {set(lead.keys())}"
        assert not (forbidden_keys & set(lead.keys()))
        # raw text / fabricated contact never stored
        assert raw_q not in str(lead)
        assert "test@x.io" not in str(lead)
