# Teamlead Hierarchy + Board Directive Endpoint Implementation Plan

> **For Hermes:** Implement this plan task-by-task by dispatching a fresh subagent via the `delegate_task` tool.

**Goal:** Add a `roster` hierarchy (departments + Teamleads) to every center's backend metadata AND a one-directional `POST /api/board/directive` endpoint that injects a Board directive into the same engine pipeline (priority `board`) targeting a firm's CEO, who cascades to department Teamleads. No upward path.

**Architecture:** Extend `catalog.py` `CENTERS_META` with an additive `roster` field (derived from each center's `panel`, per `docs/teamlead_backend_schema.md` §3). Add a new aiohttp POST route in `runtime.py` that validates the center, resolves its CEO (primary department lead from `roster`), writes the directive into `state["board_directives"][center]`, and spawns a background panel job with `priority:"board"` — mirroring the existing `center_session` flow. A read-only `GET /api/board/status` exposes ack state for the future ant-hill dashboard. The whole Board→CEO→Teamlead cascade is one-directional and priority-elevated; firms cannot push back through this channel.

**Tech Stack:** Python 3, aiohttp (`web.Application`, `app.router.add_post`), existing `state.json` persistence (`STATE_DIR/state.json`, global `state` dict, `save_state`), existing `require_key`/`spawn_background`/`run_panel_job` helpers. No new dependencies.

**Design reference (read first):** `docs/teamlead_backend_schema.md` (committed). Section 3 roster shape, Section 7 Board channel.

---

## Current context (confirmed by reading the code)

- `factory/catalog.py:864` `build_panel(slug, seed, max_panel=4)` returns a flat list of agent slugs (max 4). `CENTERS_META` built at `catalog.py:1628` stores `"panel": build_panel(...)` per center. No role/department concept today.
- `factory/runtime.py:45` `DB = Path(STATE_DIR) / "state.json"`; global `state` dict; `save_state(state)` persists. `state["jobs"]` holds panel runs; `state["leads"]` holds CRM leads.
- `factory/runtime.py:907` `center_session(request)` is the POST `/api/center` handler: validates center, `require_key`, builds `run_id`, writes `state["jobs"][run_id]`, `save_state`, `spawn_background(run_panel_job(...))`. This is the EXACT pattern to mirror for board directives.
- `factory/runtime.py:3382-3396` route registration via `app.router.add_post(...)`.
- Auth/rate-limit: `require_key(request, center)` and `require_operator(request, center, route)` already exist. The board endpoint MUST require an operator key (it is a privileged governance action) — use `require_operator`.

---

## Task 1: Add `derive_roster(panel)` + `roster` field to catalog.py

**Objective:** Every center gets an additive `roster` dict (departments + leads + experts) derived from its `panel`, so the backend carries the hierarchy without breaking existing `panel` consumers.

**Files:**
- Modify: `factory/catalog.py` (after `build_panel`, ~line 891; inside `CENTERS_META` dict comprehension, ~line 1632)

**Step 1: Write failing test**

Create: `factory/tests/test_roster.py`
```python
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
```

**Step 2: Run test to verify failure**
Run: `cd /home/eri-irfos/projects/coevolution-factory/factory && python3 -m pytest tests/test_roster.py -v`
Expected: FAIL — `AttributeError: module 'catalog' has no attribute 'derive_roster'`

**Step 3: Write minimal implementation**
Add after `build_panel` (catalog.py ~line 891):
```python
def derive_roster(panel):
    """Build the additive hierarchy from a flat panel slug list.

    One default department 'general'; its lead is panel[0] (the center's
    primary lead / CEO), the rest are experts. Additive only — does not
    replace `panel`. Mirrors docs/teamlead_backend_schema.md §3 + §5.
    """
    panel = list(panel or [])
    if not panel:
        return {"departments": []}
    lead = {"agent": panel[0], "name": panel[0], "role": "lead"}
    experts = [{"agent": p, "name": p, "role": "expert"} for p in panel[1:]]
    return {"departments": [{"id": "general", "name": "General", "lead": lead, "experts": experts}]}
```

In `CENTERS_META` dict comprehension (catalog.py ~line 1632, after `"panel": build_panel(...)`), add:
```python
    "roster": derive_roster(build_panel(c["slug"], c["seed_agents"])),
```

**Step 4: Run test to verify pass**
Run: `cd /home/eri-irfos/projects/coevolution-factory/factory && python3 -m pytest tests/test_roster.py -v`
Expected: 3 passed

**Step 5: Commit**
```bash
git add factory/catalog.py factory/tests/test_roster.py
git commit -m "feat(catalog): add derive_roster + roster field per center"
```

---

## Task 2: Initialize `board_directives` in state + CEO resolver helper

**Objective:** Ensure `state["board_directives"]` exists on load, and add a small helper to resolve a center's CEO slug from its `roster`.

**Files:**
- Modify: `factory/runtime.py` (near `state` init ~line 45; near `center_session` ~line 926)

**Step 1: Write failing test**

Create: `factory/tests/test_board_helpers.py`
```python
import runtime, catalog

def test_state_has_board_directives():
    assert "board_directives" in runtime.state

def test_resolve_ceo_returns_primary_lead():
    slug = "gdpr-guard"
    ceo = runtime.resolve_ceo(slug)
    lead = catalog.CENTERS_META[slug]["roster"]["departments"][0]["lead"]["agent"]
    assert ceo == lead
```

**Step 2: Run test to verify failure**
Run: `cd /home/eri-irfos/projects/coevolution-factory/factory && python3 -m pytest tests/test_board_helpers.py -v`
Expected: FAIL — `AttributeError: module 'runtime' has no attribute 'resolve_ceo'`

**Step 3: Write minimal implementation**
In `runtime.py` near where `state` is loaded (after `DB = Path(STATE_DIR)/"state.json"`, ~line 45), ensure the key exists:
```python
state.setdefault("board_directives", {})
```
(place right after the existing `state = json.load(...)` / `state = {}` init block).

Add a helper near `center_session` (~line 926):
```python
def resolve_ceo(slug):
    """Primary lead (CEO) of a center = lead of its first roster department."""
    roster = CENTERS.get(slug, {}).get("roster", {})
    deps = roster.get("departments") or []
    if not deps:
        return None
    return deps[0].get("lead", {}).get("agent")
```

**Step 4: Run test to verify pass**
Run: `cd /home/eri-irfos/projects/coevolution-factory/factory && python3 -m pytest tests/test_board_helpers.py -v`
Expected: 2 passed

**Step 5: Commit**
```bash
git add factory/runtime.py factory/tests/test_board_helpers.py
git commit -m "feat(state): init board_directives + resolve_ceo helper"
```

---

## Task 3: Add `POST /api/board/directive` handler

**Objective:** Privileged, one-directional endpoint that records a Board directive and injects a priority `board` panel job targeting the firm's CEO.

**Files:**
- Modify: `factory/runtime.py` (new async handler after `center_session`, ~line 936; register route ~line 3396)

**Step 1: Write failing test**

Append to `factory/tests/test_board_helpers.py`:
```python
def test_board_directive_endpoint_requires_key(client):
    # aiohttp test client posting without key -> 401/403
    resp = client.post("/api/board/directive", json={"center": "gdpr-guard", "directive": "x"})
    assert resp.status in (401, 403)
```

NOTE: if no aiohttp test client fixture exists, instead test the handler logic directly by calling `runtime.board_directive({"center":"gdpr-guard","directive":"Prioritize DPIA <1h"}, acct="board")` and asserting `state["board_directives"]["gdpr-guard"]` grew by 1 and a `priority:"board"` job was registered. Use the direct-call form to avoid fixture setup:

```python
def test_board_directive_registers_and_spawns():
    before = len(runtime.state["board_directives"].get("gdpr-guard", []))
    out = runtime.board_directive_handler_logic("gdpr-guard", "Prioritize DPIA turnaround under 1h", acct="board")
    after = runtime.state["board_directives"]["gdpr-guard"]
    assert len(after) == before + 1
    assert after[-1]["status"] == "routed_to_ceo"
    assert after[-1]["ceo_ack"] is True
```

**Step 2: Run test to verify failure**
Run: `python3 -m pytest tests/test_board_helpers.py::test_board_directive_registers_and_spawns -v`
Expected: FAIL — `AttributeError: module 'runtime' has no attribute 'board_directive_handler_logic'`

**Step 3: Write minimal implementation**
Add handler logic (refactor so the route wrapper is thin). Place after `center_session` (~line 936):
```python
def board_directive_handler_logic(center, directive, acct="board"):
    """Record a Board directive and inject a priority-board panel job.

    One-directional: Board -> CEO only. The CEO (primary roster lead) is the
    job target; run_panel_job cascades to department Teamleads. No firm->Board
    path exists. Mirrors docs/teamlead_backend_schema.md §7."""
    c = CENTERS.get(center)
    if not c:
        return None
    ceo = resolve_ceo(center)
    did = "d-" + secrets.token_hex(8)
    rec = {
        "id": did, "directive": directive[:500], "issued": int(time.time()),
        "status": "routed_to_ceo", "ceo_ack": True, "teamlead_acks": 0,
        "priority": "board", "center": center,
    }
    runtime_state().setdefault("board_directives", {}).setdefault(center, []).append(rec)
    save_state(runtime_state())
    # inject into the same engine pipeline, priority elevated
    panel = c["panel"]
    run_id = "run_" + secrets.token_hex(10)
    runtime_state().setdefault("jobs", {})[run_id] = {
        "center": center, "status": "queued", "created": int(time.time()),
        "text": directive[:500], "panel": panel, "result": None, "error": None,
        "priority": "board", "board_directive_id": did,
    }
    save_state(runtime_state())
    spawn_background(run_panel_job(run_id, center, directive, panel, c, acct))
    return {"directive_id": did, "run_id": run_id, "ceo": ceo, "status": "routed_to_ceo"}
```
(where `runtime_state()` returns the global `state` dict — use the module global `state` directly; if a helper name differs, reference the actual global.)

Add the aiohttp route handler (thin wrapper) after `center_session`:
```python
async def board_directive(request):
    center = (request.query.get("center") or (await _safe_body(request)).get("center", "")) if request.query.get("center") else ""
    try:
        body = await request.json()
    except Exception:
        body = {}
    center = center or body.get("center", "")
    c = CENTERS.get(center)
    if not c:
        return web.json_response({"error": "unknown center"}, status=404)
    acct, err = await require_operator(request, center, "board_directive")
    if err:
        return err
    directive = (body.get("directive") or "").strip()
    if not directive:
        return web.json_response({"error": "missing 'directive'"}, status=400)
    out = board_directive_handler_logic(center, directive, acct=acct)
    return web.json_response(out)
```
(If `require_operator` signature differs, match the existing call used in other POST routes; the plan's intent is: privileged key + rate-limit gate.)

**Step 4: Run test to verify pass**
Run: `python3 -m pytest tests/test_board_helpers.py -v`
Expected: all pass

**Step 5: Register the route** (runtime.py ~line 3396, after the other `add_post` lines):
```python
app.router.add_post("/api/board/directive", board_directive)
```

**Step 6: Commit**
```bash
git add factory/runtime.py factory/tests/test_board_helpers.py
git commit -m "feat(api): POST /api/board/directive one-directional board->ceo channel"
```

---

## Task 4: Add read-only `GET /api/board/status` (for future dashboard)

**Objective:** Expose board directive ack state per center so the ant-hill telemetry dashboard can read it without mutation.

**Files:**
- Modify: `factory/runtime.py` (new handler ~after Task 3 handler; register GET route)

**Step 1: Write failing test**
```python
def test_board_status_returns_directives():
    runtime.state.setdefault("board_directives", {})["gdpr-guard"] = [
        {"id": "d-1", "status": "routed_to_ceo", "ceo_ack": True, "teamlead_acks": 1}]
    out = runtime.board_status("gdpr-guard")
    assert out["center"] == "gdpr-guard"
    assert out["directives"][0]["id"] == "d-1"
```

**Step 2: Run test to verify failure**
Run: `python3 -m pytest tests/test_board_helpers.py::test_board_status_returns_directives -v`
Expected: FAIL — no attribute `board_status`

**Step 3: Write minimal implementation**
```python
def board_status(center):
    return {
        "center": center,
        "directives": runtime_state().get("board_directives", {}).get(center, []),
    }

async def board_status_handler(request):
    center = request.query.get("center", "")
    if not CENTERS.get(center):
        return web.json_response({"error": "unknown center"}, status=404)
    return web.json_response(board_status(center))
```
Register: `app.router.add_get("/api/board/status", board_status_handler)`

**Step 4: Run test to verify pass**
Run: `python3 -m pytest tests/test_board_helpers.py -v`
Expected: all pass

**Step 5: Commit**
```bash
git add factory/runtime.py factory/tests/test_board_helpers.py
git commit -m "feat(api): GET /api/board/status read-only governance telemetry"
```

---

## Task 5: Pre-flight + push + deploy

**Objective:** Prove the whole app still imports/renders and the new routes are wired; ship.

**Step 1: Local pre-flight**
```bash
cd /home/eri-irfos/projects/coevolution-factory/factory
python3 - <<'PY'
import sys; sys.path.insert(0,'.')
import runtime, catalog
# roster present on every center
assert all(catalog.CENTERS_META[s]["roster"]["departments"] for s in catalog.CENTERS_META), "every center needs a roster"
# board directive round-trip
runtime.state.setdefault("board_directives", {})
out = runtime.board_directive_handler_logic("gdpr-guard", "Prioritize DPIA turnaround under 1h", acct="board")
assert out["ceo"] == catalog.CENTERS_META["gdpr-guard"]["roster"]["departments"][0]["lead"]["agent"]
assert runtime.board_status("gdpr-guard")["directives"][-1]["id"] == out["directive_id"]
# modal still renders
h = runtime.center_card_html("gdpr-guard", "de")
assert "Produkte & Leistungen" in h
print("PREFLIGHT OK")
PY
python3 -m pytest tests/ -q
```
Expected: `PREFLIGHT OK` + tests pass.

**Step 2: Commit any test scaffolding, push**
```bash
cd /home/eri-irfos/projects/coevolution-factory
git add -A && git commit -m "test: board channel + roster coverage" || echo "nothing to commit"
git push origin master
```

**Step 3: Deploy (Fly retry loop)**
```bash
cd /home/eri-irfos/projects/coevolution-factory/factory
export PATH="$HOME/.fly/bin:$PATH"
APP=coevolution-factory-sparkling-mountain-1802
for i in $(seq 1 20); do
  out=$(fly deploy -a "$APP" -c fly.toml --remote-only 2>&1)
  echo "$out" | tail -1
  if echo "$out" | grep -qiE "Visit your newly deployed app|deployed|complete"; then echo "DEPLOY_OK attempt $i"; break; fi
  sleep 30
done
```

**Step 4: Live smoke**
```bash
python3 - <<'PY'
import urllib.request, json
BASE="https://coevolution-factory-sparkling-mountain-1802.fly.dev"
# roster present in meta? check a center card still renders products
html=urllib.request.urlopen(f"{BASE}/gdpr-guard?lang=de", timeout=25).read().decode()
print("products block live:", 'Produkte & Leistungen' in html)
# board status endpoint (no directive yet -> empty list, 200)
import urllib.request
try:
    r=urllib.request.urlopen(f"{BASE}/api/board/status?center=gdpr-guard", timeout=25)
    print("board status:", r.status, json.loads(r.read())["center"])
except Exception as e:
    print("board status endpoint:", e)
PY
```
Expected: `products block live: True` and board status returns 200 with `center: gdpr-guard`.

---

## Risks / tradeoffs / open questions

- **CEO resolution is simplistic** (panel[0] / first roster department lead). The doc allows explicit leads later; v1 derives. Fine for the channel to work.
- **`run_panel_job` signature** must accept the same args used by `center_session` (`run_id, center, text, panel, c, acct`). Mirror exactly; if `acct` isn't threaded into `run_panel_job`, pass it positionally/as the existing last arg (check `center_session` call at runtime.py:933).
- **Auth:** board endpoint uses `require_operator` (key + rate-limit). Confirm the operator key mechanism exists; if only `require_key` exists, use that — but document that board directives are privileged.
- **State persistence:** `board_directives` lives in `state.json` (persisted), so directives survive restart — matches doc §7.3.
- **No upward path:** there is deliberately NO firm→board POST route. Enforce by not adding one.
- **YAGNI:** dashboard UI itself is OUT of scope (separate task). This plan only builds the data model + endpoints the dashboard will later read.
