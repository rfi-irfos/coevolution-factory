"""Observatory scale-out view test (Task 5).

conftest.py freezes FT_STATE_DIR to a temp dir and puts factory/ on
sys.path so `import runtime` works. TDD: failing test -> implement -> green.

Asserts:
  1. The rendered /observatory HTML contains a "Scale-out" section.
  2. The daughter-center count is surfaced in that section.
  3. The JSON contract stays 100% intact (Accept: application/json) and
     now carries a `scaleout_promoted` count + daughter count.
"""
import asyncio


class _FakeRequest:
    """Minimal aiohttp-like request: no app loop, no real HTTP."""

    def __init__(self, headers=None):
        self.headers = headers or {}
        self.query = {}
        self._match = {}
        self.remote = "127.0.0.1"

    @property
    def match_info(self):
        return self._match


def test_observatory_has_scaleout_section():
    import runtime as R

    # Seed two daughter centers so the count is non-zero and visible.
    R.state["daughter_centers"] = {"da": {}, "db": {}}

    async def _run():
        req = _FakeRequest(headers={})  # human path -> HTML
        res = await R.observatory(req)
        body = res.text if hasattr(res, "text") else res.body.decode()
        assert "Scale-out" in body, "no Scale-out section in observatory HTML"
        # daughter count must render in the section
        assert "<b>2</b> daughters" in body, "daughter count not surfaced in HTML"

    asyncio.run(_run())


def test_observatory_json_contract_intact():
    import runtime as R

    R.state["daughter_centers"] = {"da": {}, "db": {}}

    async def _run():
        req = _FakeRequest(headers={"Accept": "application/json"})
        res = await R.observatory(req)
        import json
        payload = json.loads(res.body.decode())
        # existing contract keys still present
        for k in ("centers_total", "centers_active", "total_sessions",
                  "spawn_candidates", "virtual_firm"):
            assert k in payload, f"JSON contract lost key: {k}"
        # new scale-out fields
        assert "scaleout_promoted" in payload, "no scaleout_promoted in JSON"
        assert payload.get("daughters_total") == 2, "daughter count wrong"

    asyncio.run(_run())
