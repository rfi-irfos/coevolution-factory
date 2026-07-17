# Autonomous Daughter Scale-Out — Phase 2 Implementation Plan

> **For Hermes:** Implement this plan task-by-task by dispatching a fresh subagent via the `delegate_task` tool.

**Goal:** Scale the CoEvolution Factory's daughter centers autonomously and safely — batch Laura-gating, capacity-aware spawning, auto-networking between daughters, and a scale-out Observatory view — while keeping Laura as the FINAL ship gate and never self-approving.

**Architecture:** Today each staged candidate is gated by one serial `mcp_laura_review_plan` call in `daily_spawn.main()` (bottleneck at N calls). Phase 2 adds: (1) a single BATCH Laura review over all staged candidates instead of N serial calls; (2) a capacity/health pre-check so we never spawn past engine/app limits; (3) auto-population of `CENTER_NETWORK` edges between co-emerging daughters; (4) a `scale_out()` orchestrator that runs the full loop (scan → batch-gate → promote → network → observe) with bounded concurrency (turntable pattern); (5) an Observatory "Scale-out" section. All gating stays Laura-gated; `launch_staged_offering` (Virtual Firm) already covers self-launch and is untouched.

**Tech Stack:** Python 3.14, aiohttp, existing `daily_spawn.py` (`gate_candidate`, `promote`, `apply_second_reviewer`), `factory_spawn_agent.py` (`run_spawn_agent`), `virtual_firm.py`, `runtime.py` (`CENTERS`, `CENTER_NETWORK`, `state`). Tests: `pytest` (37 passing baseline; target 45+).

---

## Current context / assumptions

- `factory/daily_spawn.py`: `gate_candidate(cand)` does ONE Laura MCP call; `main()` loops candidates serially (line 126-140).
- `factory/factory_spawn_agent.py`: `run_spawn_agent()` reads real RSS/trend feeds, stages `spawn_candidates` (no auto-apply).
- `factory/virtual_firm.py`: `launch_staged_offering(oid)` — reversible self-launch, all-gates-true. UNTOUCHED by this plan.
- `factory/runtime.py`: `CENTER_NETWORK` (adjacency), `state["daughter_centers"]`, rehydrate at boot (line 95), `/observatory` HTML (line 1051+).
- Secrets live: `VF_AUTO_LAUNCH=1`, `HITL_SECOND_REVIEWER=simeon-appointed`.
- `mcp_laura_review_plan` may be `None` (Laura offline) → gate returns False (no self-approve).
- Constraint (Milestone 2026-07-16): NO burst parallelism on the engine key — serial "turntable" pattern (concurrency 1) for engine calls.

---

## Proposed approach

1. Add `batch_gate_candidates(cands)` → ONE Laura call reviewing all staged candidates; returns `{slug: bool}` pass-map. Falls back to per-candidate `gate_candidate` if Laura lacks batch support (keep old path working).
2. Add `capacity_ok()` → checks engine health + app 0-status count + a `VF_MAX_DAUGHTERS` env cap before promoting.
3. Add `network_daughters(new_slugs)` → links co-spawned daughters in `CENTER_NETWORK` (adjacency both ways) + to parent.
4. Add `scale_out()` orchestrator in `daily_spawn.py`: scan → batch-gate → capacity filter → promote (serial, turntable) → network → return report.
5. Wire `scale_out()` into `daily_spawn.main()` (replace the serial loop).
6. Add Observatory "Scale-out" HTML section (counts: standing / daughters / staged / launched + last scale-out report).
7. TDD each, frequent commits, full suite green at end.

---

## Step-by-step plan

### Task 1: Batch Laura gate (single call, all candidates)

**Objective:** Replace N serial Laura calls with one batch review; keep per-candidate fallback.

**Files:**
- Modify: `factory/daily_spawn.py:44` (add `batch_gate_candidates` after `gate_candidate`)
- Test: `tests/test_scaleout.py` (new)

**Step 1: Write failing test**

```python
def test_batch_gate_returns_passmap(monkeypatch):
    import daily_spawn as DS
    cands = {
        "a": {"name": "A", "mandate": "x", "uncovered_signals": []},
        "b": {"name": "B", "mandate": "y", "uncovered_signals": []},
    }
    # fake Laura that flags candidate 'b'
    class FakeRes:
        def __init__(self, flags): self.flags = flags
    def fake(text, title, metadata, **kw):
        slug = metadata["slug"]
        return {"flags": ["x"] if slug == "b" else []}
    monkeypatch.setattr(DS, "mcp_laura_review_plan", fake)
    out = DS.batch_gate_candidates(cands)
    assert out == {"a": True, "b": False}
```

**Step 2: Run to verify failure**
`pytest tests/test_scaleout.py::test_batch_gate_returns_passmap -v` → FAIL (no `batch_gate_candidates`).

**Step 3: Implement**

```python
async def batch_gate_candidates(cands):
    """One Laura call reviewing all staged candidates. Returns {slug: bool}.
    Falls back to per-candidate gate_candidate if Laura MCP is unavailable."""
    if mcp_laura_review_plan is None:
        return {s: False for s in cands}
    try:
        res = mcp_laura_review_plan(
            title="AutoCenter spawn batch review",
            text=json.dumps([
                {"slug": s, "name": c.get("name"),
                 "mandate": c.get("mandate"),
                 "uncovered_signals": c.get("uncovered_signals", [])}
                for s, c in cands.items()
            ], indent=2),
            metadata={"kind": "factory-spawn-batch",
                       "count": len(cands)},
        )
        # accept either a top-level flags list or per-candidate verdicts
        if isinstance(res, dict) and "verdicts" in res:
            verdicts = res["verdicts"]
            return {s: (verdicts.get(s, {}).get("flags", []) == [])
                    for s in cands}
        flags = res.get("flags", []) if isinstance(res, dict) else []
        # single top-level flags list -> all-or-nothing (conservative)
        return {s: (len(flags) == 0) for s in cands}
    except Exception:
        # fallback: per-candidate (serial) so one Laura error doesn't kill all
        return {s: await gate_candidate(c) for s, c in cands.items()}
```

**Step 4: Run to verify pass**
`pytest tests/test_scaleout.py::test_batch_gate_returns_passmap -v` → PASS

**Step 5: Commit**
`git commit -m "feat(scaleout): batch Laura gate for staged candidates"`

---

### Task 2: Capacity / health pre-check

**Objective:** Never promote past engine/app limits; respect a max-daughters cap.

**Files:**
- Modify: `factory/daily_spawn.py` (add `capacity_ok`)
- Test: `tests/test_scaleout.py`

**Step 1: Write failing test**

```python
def test_capacity_ok_respects_cap(monkeypatch):
    import daily_spawn as DS
    import runtime as R
    monkeypatch.setenv("VF_MAX_DAUGHTERS", "2")
    R.state["daughter_centers"] = {"d1": {}, "d2": {}}  # already at cap
    assert DS.capacity_ok() is False
    R.state["daughter_centers"] = {"d1": {}}
    assert DS.capacity_ok() is True
```

**Step 2: Run to verify failure** → FAIL (no `capacity_ok`).

**Step 3: Implement**

```python
_MAX_DAUGHTERS = int(os.environ.get("VF_MAX_DAUGHTERS", "10"))

def capacity_ok():
    """True if we may promote more daughters this cycle.
    Respects VF_MAX_DAUGHTERS cap and refuses while any center is 0-status
    (engine unreachable) so we don't scale into a degraded state."""
    daughters = len(R.state.get("daughter_centers", {}))
    if daughters >= _MAX_DAUGHTERS:
        return False
    # refuse if any center is in 0-status (engine down)
    for st in R.state.get("center_status", {}).values():
        if st.get("status") == "0-status":
            return False
    return True
```

**Step 4: Run to verify pass** → PASS

**Step 5: Commit** `git commit -m "feat(scaleout): capacity/health pre-check before promote"`

---

### Task 3: Auto-network co-spawned daughters

**Objective:** Link daughters that spawn in the same cycle (and to parent) in `CENTER_NETWORK`.

**Files:**
- Modify: `factory/daily_spawn.py` (add `network_daughters`)
- Test: `tests/test_scaleout.py`

**Step 1: Write failing test**

```python
def test_network_daughters_links_both_ways():
    import daily_spawn as DS
    import runtime as R
    R.CENTER_NETWORK.clear()
    DS.network_daughters(["gdpr-guard"], ["da", "db"])
    assert "db" in R.CENTER_NETWORK["da"]
    assert "da" in R.CENTER_NETWORK["db"]
    assert "da" in R.CENTER_NETWORK["gdpr-guard"]
```

**Step 2: Run to verify failure** → FAIL.

**Step 3: Implement**

```python
def network_daughters(parent, new_slugs):
    """Link co-spawned daughters to each other and to the parent in
    CENTER_NETWORK (adjacency is bidirectional). Idempotent."""
    for s in new_slugs:
        R.CENTER_NETWORK.setdefault(s, [])
        if parent and parent not in R.CENTER_NETWORK[s]:
            R.CENTER_NETWORK[s].append(parent)
        if parent and s not in R.CENTER_NETWORK.setdefault(parent, []):
            R.CENTER_NETWORK[parent].append(s)
        for o in new_slugs:
            if o != s and o not in R.CENTER_NETWORK[s]:
                R.CENTER_NETWORK[s].append(o)
```

**Step 4: Run to verify pass** → PASS

**Step 5: Commit** `git commit -m "feat(scaleout): auto-network co-spawned daughters"`

---

### Task 4: scale_out() orchestrator

**Objective:** One function runs the full loop: scan → batch-gate → capacity filter → promote (serial turntable) → network → report.

**Files:**
- Modify: `factory/daily_spawn.py` (add `scale_out`, replace `main` loop with call to it)
- Test: `tests/test_scaleout.py`

**Step 1: Write failing test**

```python
def test_scale_out_promotes_passed_and_caps(monkeypatch):
    import daily_spawn as DS
    import runtime as R
    R.state["daughter_centers"] = {}
    R.state["spawn_candidates"] = {
        "da": {"name": "A", "mandate": "x", "status": "staged",
               "slug": "da", "parent": "gdpr-guard",
               "uncovered_signals": []},
        "db": {"name": "B", "mandate": "y", "status": "staged",
               "slug": "db", "parent": "gdpr-guard",
               "uncovered_signals": []},
    }
    # Laura passes both
    monkeypatch.setattr(DS, "mcp_laura_review_plan", lambda **kw: {"flags": []})
    monkeypatch.setattr(DS, "run_spawn_agent",
                        lambda: {"staged": 2})
    report = DS.scale_out()
    assert report["promoted"] == ["da", "db"]
    assert "da" in R.CENTERS and "db" in R.CENTERS
```

**Step 2: Run to verify failure** → FAIL.

**Step 3: Implement**

```python
async def scale_out():
    """Autonomous scale-out loop (turntable: serial engine calls).
    scan -> batch-gate -> capacity filter -> promote -> network -> report.
    Laura stays FINAL gate; capacity_ok() guards health + cap."""
    scan_res = await F.run_spawn_agent()
    st = load_state()
    staged = {s: c for s, c in st.get("spawn_candidates", {}).items()
              if c.get("status") == "staged"}
    promoted, blocked = [], []
    if staged and capacity_ok():
        passmap = await batch_gate_candidates(staged)
        new_slugs = []
        for slug, cand in staged.items():
            if passmap.get(slug):
                ok = promote(st, cand)
                cand["status"] = "born" if ok else "duplicate"
                cand["laura_pass"] = True
                DS_apply_reviewer(cand)  # additive HITL slot
                if ok:
                    promoted.append(slug)
                    new_slugs.append(slug)
            else:
                cand["status"] = "blocked_pending_laura"
                blocked.append(slug)
        # network co-spawned daughters to each other + parent
        parents = {c.get("parent") for c in staged.values()}
        for p in parents:
            network_daughters(p, new_slugs)
    save_state(st)
    return {"scan": scan_res, "promoted": promoted,
            "blocked_pending_laura": blocked,
            "capacity_ok": capacity_ok()}
```

Note: `DS_apply_reviewer` = `apply_second_reviewer` (imported in-module). Replace `main()` body (lines 121-148) to call `await scale_out()` and print the JSON report.

**Step 4: Run to verify pass** → PASS

**Step 5: Commit** `git commit -m "feat(scaleout): scale_out() orchestrator replaces serial loop"`

---

### Task 5: Observatory scale-out view

**Objective:** Surface scale-out state in `/observatory` HTML.

**Files:**
- Modify: `factory/runtime.py` `_observatory_html` (add Scale-out section) + `observatory()` payload
- Test: `tests/test_observatory_scaleout.py` (new)

**Step 1: Write failing test**

```python
def test_observatory_has_scaleout_section():
    import runtime as R
    html = R._observatory_html(R.observatory_payload_for_test())  # helper or build payload
    assert "Scale-out" in html
```

(Subagent: add a small test helper or build payload inline; assert the section + daughter count render.)

**Step 2: Implement** — in `_observatory_html`, after Spawn candidates table, add:
```html
<h2>Scale-out</h2>
<div class=card>
  {payload["centers_total"]} standing · {len(payload.get("daughter_centers",{}))} daughters ·
  {payload.get("scaleout_promoted",0)} promoted last cycle
</div>
```
Add `scaleout_promoted` to the JSON payload in `observatory()`.

**Step 3: Run** → PASS

**Step 4: Commit** `git commit -m "feat(scaleout): Observatory scale-out section"`

---

### Task 6: Full suite + deploy + verify

**Objective:** Green suite, deployed, live health check.

**Files:** all above.

**Step 1:** `FT_STATE_DIR=/tmp/ft pytest tests/ -v` → expect 45+ passed.
**Step 2:** `git push origin master`
**Step 3:** `fly deploy --app coevolution-factory-sparkling-mountain-1802 -y`
**Step 4:** verify `/health` mode:live + `/observatory` shows Scale-out.

---

## Files likely to change

- `factory/daily_spawn.py` — `batch_gate_candidates`, `capacity_ok`, `network_daughters`, `scale_out`, `main` loop.
- `factory/runtime.py` — observatory payload + HTML scale-out section.
- `tests/test_scaleout.py` (new), `tests/test_observatory_scaleout.py` (new).
- `factory/docs/OPERATIONS.md` — add §7 Scale-out (batch gate, capacity cap `VF_MAX_DAUGHTERS`, network behavior).

## Tests / validation

- `tests/test_scaleout.py`: batch gate pass-map, capacity cap, network both-ways, scale_out promotes+network+caps.
- `tests/test_observatory_scaleout.py`: Scale-out section renders.
- Baseline 37 → target 45+ passed.
- Live: `/health` mode:live, `/observatory` Scale-out section present.

## Risks, tradeoffs, open questions

- **Laura batch support:** if `mcp_laura_review_plan` has no batch mode, `batch_gate_candidates` falls back to serial (no behavior regression). OPEN: confirm Laura MCP accepts a list payload — if not, keep serial but it's already the current behavior.
- **Capacity cap:** `VF_MAX_DAUGHTERS` default 10 — tune with Simeon. Too low = no scaling; too high = engine cost.
- **0-status refusal:** `capacity_ok` refuses while any center is 0-status. Could stall scaling during transient engine blips — acceptable (safe default).
- **Networking:** auto-linking daughters could create a dense graph; capped naturally by per-cycle spawn count.
- **No new secrets required** beyond existing `VF_AUTO_LAUNCH` / `HITL_SECOND_REVIEWER`; `VF_MAX_DAUGHTERS` is optional (defaults).
- **Virtual Firm self-launch untouched** — this plan scales the spawn-agent + propose paths; `launch_staged_offering` remains the reversible self-launch for Virtual Firm offerings.
