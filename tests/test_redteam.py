"""Red-team suite for the CoEvolution Factory (offline, no live HTTP).

Authorized DEFENSIVE red-team of OWN service (rfi-irfos-infra-hardening
doctrine): read-only probes against our own code, NO mutating/costly
calls, NO secrets. Each test asserts one of the 5 vuln classes from the
stack checklist:

1. Unauthenticated operator routes -> 401 without a key.
2. Reflected XSS -> malicious param escaped, never raw.
3. Spawn containment -> no duplicate / no path traversal.
4. No-PII leads -> raw incoming text is hashed, never stored.
5. Resilience -> center serves 200 (cached) in degraded/0-status, never 500.

All run offline: engine + keys are monkeypatched/injected. If a real
vuln is found, the test FAILS and we report it — we do NOT exploit.
"""
import os
import sys
import json
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import factory_spawn_agent  # noqa: E402  (import side-effect harmless)
import runtime as R  # noqa: E402


class _FakeRequest:
    """Minimal aiohttp-like request: no app loop, no real HTTP."""
    def __init__(self, headers=None, query=None, body=None):
        self.headers = headers or {}
        self.query = query or {}
        self._body = body or {}
        self._match = {}
        self.remote = "127.0.0.1"

    async def json(self):
        return self._body

    @property
    def match_info(self):
        return self._match


async def _auth_err(request, center):
    """Replicate require_key behavior without running the app server."""
    acct, err = await R.require_key(request, center)
    return err


def test_unauth_operator_routes():
    """Finding class 1: every operator route must 401 without a key."""
    req = _FakeRequest(headers={})  # no Authorization
    for center in ["gdpr-guard", "ai-act-guard"]:
        err = asyncio.run(_auth_err(req, center))
        assert err is not None, f"{center} operator route accepted no key"
        assert err.status == 401, f"{center} should 401, got {err.status}"


def test_no_reflected_xss():
    """Finding class 2: index search query is escaped in rendered HTML.

    center_page has many required center-dict keys; the reflected-input
    surface that actually takes attacker-controlled data is the index
    search box (?q=). Assert it is HTML-escaped (the html.escape fix).
    """
    async def _run():
        req = _FakeRequest(query={"q": "<script>alert(1)</script>"})
        res = await R.index(req)
        body = res.text if hasattr(res, "text") else res.body.decode()
        assert "<script>alert(1)</script>" not in body, "RAW script reflected in ?q!"
        assert "&lt;script&gt;" in body, "search query not HTML-escaped"

    asyncio.run(_run())


def test_spawn_containment():
    """Finding class 3: spawn_session validates input, never convenes a
    fabricated agent, and daughter-center creation guards duplicate slugs.

    spawn_session (intra-company team path) must reject: no key, no text,
    no valid gap agent. Duplicate daughter-CENTER slugs are guarded in the
    evolve path (runtime.py: `if new_slug in CENTERS`)."""
    async def _run():
        orig = R.require_key
        async def _pass(req, c):
            return ({"center": "gdpr-guard"}, None)
        R.require_key = _pass  # pass
        try:
            # missing text -> 400
            req = _FakeRequest(
                headers={"Authorization": "Bearer x"},
                query={"center": "gdpr-guard"},
                body={"gap_agents": ["x"]},
            )
            res = await R.spawn_session(req)
            assert res.status == 400, f"missing text not rejected: {res.status}"

            # fabricated agent (not in registry) -> 400, never convened
            req2 = _FakeRequest(
                headers={"Authorization": "Bearer x"},
                query={"center": "gdpr-guard"},
                body={"text": "x", "gap_agents": ["__fabricated_agent__"]},
            )
            res2 = await R.spawn_session(req2)
            assert res2.status == 400, f"fabricated agent not rejected: {res2.status}"
        finally:
            R.require_key = orig

    asyncio.run(_run())


def test_spawn_unknown_center_404():
    """Finding class 3b: spawn against an unknown center -> 404, no leak."""
    async def _run():
        req = _FakeRequest(headers={}, query={"center": "../etc/passwd"})
        res = await R.spawn_session(req)
        assert res.status == 404, f"unknown center not 404: {res.status}"

    asyncio.run(_run())


def test_lead_no_pii():
    """Finding class 4: add_lead hashes text; raw text never stored."""
    R.state.setdefault("leads", {}).setdefault("gdpr-guard", [])
    R.add_lead("gdpr-guard", "session", "run_x", "my secret SSN 1234",
               outcome="demo")
    lead = R.state["leads"]["gdpr-guard"][-1]
    assert "my secret SSN 1234" not in json.dumps(lead), "RAW PII stored!"
    assert lead.get("question_hash"), "no question_hash"
    assert len(lead["question_hash"]) == 64, "not sha256"


def test_resilience_200_when_degraded():
    """Finding class 5: degraded center still serves 200 (cached), not 500."""
    R.set_center_status("gdpr-guard", "degraded", detail="red-team sim")

    async def _run():
        R.state.setdefault("keys", {})["k"] = {"center": "gdpr-guard"}
        orig = R.require_key
        async def _pass(req, c):
            return (R.state["keys"]["k"], None)
        R.require_key = _pass
        try:
            req = _FakeRequest(headers={"Authorization": "Bearer k"})
            req._match = {"slug": "gdpr-guard"}
            res = await R.center_page_handler(req)
            assert res.status == 200, f"degraded center not 200: {res.status}"
            body = res.body.decode() if hasattr(res.body, "decode") else str(res.body)
            assert "reduced mode" in body.lower() or "degraded" in body.lower(), \
                "no honest reduced-mode note"
        finally:
            R.require_key = orig

    asyncio.run(_run())
    R.set_center_status("gdpr-guard", "healthy", detail="red-team cleared")
