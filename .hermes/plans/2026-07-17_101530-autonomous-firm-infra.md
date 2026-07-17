# CoEvolution "Autonomous Firm" Infrastructure — Implementation Plan

> **For Hermes:** Implement this plan task-by-task by dispatching a fresh
> subagent via the `delegate_task` tool. THIS IS PLAN MODE — no execution
> happens until Simeon + Laura approve and say go.

**Goal:** Turn the 51 (and growing) centers into a self-sustaining "virtual
firm" — an agentic, data-processing-only organization (NO physical product,
NO real-company takeover; the earlier "Apple" wording was a parable for
"large firm with funnels + pipelines from MVP to production", not a literal
Fortune-500 replacement). Centers debate shared problems, survive engine
outages in a safe "0-status" (degraded, not offline), each tracks its own
leads/CRM from REAL visitor traffic, and a product pipeline (idea → debate →
prototype → staged → launched) moves offerings from MVP to production — all
autonomously under a ≥2-human HITL watch, never silently faking data or
bypassing the Laura gate.

**Architecture:** Extend the existing `runtime.py` + `synthesis.py` + `catalog.py`
on top of the already-present `CENTER_NETWORK` adjacency and `propagate_tensions`.
Three new subsystems, each independently shippable and Laura-gated where it
touches spawning/money:
1. **Debate** — a convener that takes a tension + the adjacent centers and
   produces a cross-center resolution (reuses `propagate_tensions` + a pooled
   panel). No new engine calls beyond what `/api/center` already does.
2. **Resilience / 0-status** — a per-center status FSM persisted in `state.json`.
   On engine error the center goes `degraded` (cached briefings, honest note),
   never 500/offline. Engine health is the only signal.
3. **Per-center CRM / leads** — a `leads` store per center, populated ONLY from
   real `usage`/`sessions_log` events (incoming questions + panel outcomes).
   No scraping, no PII fabrication. Exposed read-only in `/observatory`.
4. **Virtual Firm R0hne (product pipeline)** — an agentic, data-processing-only
   org model. A pipeline stage machine per offering:
   `idea → debate → prototype → staged → launched`. "Launched" = a new center
   (via FACTORY-FACTORY) or a new product offering, ALWAYS Laura-gated at the
   `staged → launched` transition. This is the MVP→production funnel: leads
   flow in (CRM), get debated (subsystem 1), resolve to a prototype, and are
   staged for Laura's sign-off before they ship. No physical product, no real
   company is "replaced" — it is our own autonomous data-processing firm.

**Tech Stack:** Python 3.12 (aiohttp), single `state.json` store on Fly volume
(no new DB), existing `lauras-agents-api` engine, `pytest` for the (currently
missing) test suite. Honest constraint: the "≥2-human HITL" gate is a
GOVERNANCE RULE, not code — the plan wires Laura as gate #1 and leaves a
second human review hook (`HITL_SECOND_REVIEWER` env) as the documented slot.

---

## Current context / assumptions (verified read-only this session)

- `factory/runtime.py` — `center_session` (235), `observatory` (647, now
  exposes `spawn_candidates`), routes at 1051-1079. State loaded from
  `state.json` on a Fly volume; `save_state` after mutations.
- `factory/synthesis.py` — `propagate_tensions(slug, synth, network)` (114)
  already tags a center's conflicts with `shared_with` = adjacent centers.
  This IS the debate seed.
- `factory/catalog.py` — `CENTER_NETWORK = build_network()` (827), mutated at
  runtime when daughters spawn (runtime.py:1044-1047). 51 centers live.
- `factory/state.json` — already holds `usage`, `payments`, `spawn_candidates`,
  `jobs`. No `center_status` / `leads` keys yet → plan adds them.
- **NO `tests/` directory exists.** AGENTS.md requires ≥80% coverage → the
  plan stands up `pytest` + `tests/` first.
- Laura MCP (`mcp_laura_review_plan`) was OFFLINE this session; HITL resolved
  in-person with Simeon + Laura at the screen. Spawning/money paths MUST stay
  Laura-gated; code must not self-approve.

---

## Proposed approach (REAL vs FANTASY — flagged honestly)

| User vision | This plan builds | What it deliberately does NOT do |
|---|---|---|
| firms are chaotic, solve problems internally | Debate subsystem (real pooled panel over shared tensions) | simulate "office politics" — only real panel outputs |
| meet & debate | `/api/center/debate` convening adjacent centers | invent conversations; only engine panel text |
| 0-status without going offline | status FSM: healthy→degraded→0-status, cached serve | claim "self-healing AI" magic; it's graceful degradation |
| own CRM / leads | per-center `leads` from REAL traffic | scrape external PII or fabricate contacts |
| full autonomy = full autonomy | autonomous debate + resilience + CRM run with NO human | auto-SPAWN centers without Laura gate (stays gated) |
| "Apple replaced by our agents" | a **Virtual Firm R0hne** (agentic, data-processing
  only, labelled VIRTUAL-FIRM) — our OWN autonomous firm, NOT a real company
  takeover. Parable for "large firm with funnels + pipelines", understood. |
  claim we run a real Fortune-500 (bullshit — not done) |
| own democracy / new products | governance VOTING among panel agents + proposal staging | found a legal entity / mint equity (out of scope) |
| always HITL ≥2 + orchestra plays alone | auton. subsystems + Laura gate #1 + 2nd-reviewer slot | remove human oversight (NEVER) |

---

## Step-by-step plan

### Task 0: Stand up the test suite (TDD foundation)

**Objective:** Create `tests/` so every later task has a failing-then-passing
cycle, satisfying AGENTS.md coverage rule.

**Files:**
- Create: `tests/conftest.py` (loads `factory/` onto path, freezes FT_STATE_DIR to a tmp dir)
- Create: `tests/test_state.py`
- Create: `pytest.ini` (root) with `testpaths = tests`, `addopts = -q`

**Step 1: Write failing test**
```python
# tests/test_state.py
import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "factory"))
import importlib, factory_spawn_agent as F

def test_state_roundtrip():
    d = tempfile.mkdtemp()
    os.environ["FT_STATE_DIR"] = d
    importlib.reload(F)
    F.save_state({"x": 1})
    assert F.load_state().get("x") == 1
```

**Step 2:** Run `pytest tests/test_state.py -v` → FAIL (no tests dir / import).
**Step 3:** Create `pytest.ini` + `tests/conftest.py` minimal, re-run → PASS.
**Step 4:** Commit `feat: add pytest scaffold`.

---

### Task 1: Center status FSM + pipeline stage (the "0-status" resilience)

**Objective:** Persist a per-center status machine so a center survives engine
outage in `degraded`/`0-status` instead of 500ing. ALSO add a per-offering
pipeline stage (`idea → debate → prototype → staged → launched`) so the firm
has a real MVP→production funnel that is resilient at every stage.

**Files:**
- Modify: `factory/runtime.py` — add `CENTER_STATUS = {}` cache + `status_key(slug)`
  and `PIPELINE = {}` cache for offering stages.
- Modify: `factory/runtime.py` `run_panel_job` — on engine exception set
  `state["center_status"][slug] = "degraded"` with `last_error`; on success
  `"healthy"`.
- Modify: `factory/runtime.py` `center_page_handler` — if status is
  `degraded`/`0-status`, render cached last synthesis + an honest
  "operating in reduced mode" banner (no fake fresh verdict).
- Modify: `factory/runtime.py` `debate_session` (Task 2) — on debate resolve,
  advance the related offering's `PIPELINE` stage (`idea→debate→prototype`).
- Test: `tests/test_resilience.py` (engine error → degraded + 200; pipeline
  stage advances on debate).

**Step 1 (test):**
```python
def test_degraded_on_engine_error(monkeypatch):
    # force engine_synthesize to raise; assert status == degraded
    # and center_page still returns 200 with cached note

def test_pipeline_advances_on_debate():
    # seed offering at 'idea'; run debate; assert stage == 'debate'
```

**Step 2:** run → FAIL. **Step 3:** implement FSM + pipeline stage + graceful
render. **Step 4:** run → PASS. **Step 5:** commit `feat: center 0-status FSM + pipeline stage`.

---

### Task 2: Inter-center debate convener

**Objective:** A端点 `/api/center/debate` that takes a tension + center, pulls
adjacent centers from `CENTER_NETWORK`, and convenes a pooled panel producing
a cross-center resolution. Reuses `propagate_tensions` for context sharing.

**Files:**
- Modify: `factory/runtime.py` — `debate_session(request)` handler (requires
  center key), builds pooled panel from `CENTER_NETWORK[center]`, calls
  `engine_synthesize`, stores `state["debates"][run_id]`.
- Modify: `factory/runtime.py` routes — `add_post("/api/center/debate", debate_session)`.
- Modify: `factory/observatory` — expose `debates` count + last resolution.
- Test: `tests/test_debate.py` (mock engine, assert adjacent centers invited).

**Step 1 (test):** assert a debate run_id is returned and adjacent centers
appear in the panel. **Step 2:** FAIL. **Step 3:** implement. **Step 4:** PASS.
**Step 5:** commit `feat: inter-center debate convener`.

---

### Task 3: Per-center CRM / leads (from REAL traffic only)

**Objective:** Track each center's leads in `state["leads"][slug]`, populated
ONLY from real `usage`/`sessions_log` events (incoming question + outcome).
Read-only in `/observatory`. No external scrape, no PII fabrication.

**Files:**
- Modify: `factory/runtime.py` `run_panel_job` — on completed job, append a
  lead `{ts, question_hash, outcome, center}` to `state["leads"][center]`.
- Modify: `factory/runtime.py` `observatory` — add `leads_count` per center
  + total.
- Test: `tests/test_crm.py` (assert a completed session creates exactly one
  lead, with no fabricated fields).

**Step 1 (test):** one completed session → one lead. **Step 2:** FAIL.
**Step 3:** implement. **Step 4:** PASS. **Step 5:** commit `feat: per-center leads from real traffic`.

---

### Task 4: Governance — second human reviewer slot + Virtual Firm R0hne

**Objective:** Document + wire the ≥2-human HITL. Laura = gate #1 (existing
`mcp_laura_review_plan`). Add `HITL_SECOND_REVIEWER` env slot (read in
`daily_spawn`/`daily_evolve` gating) + a **Virtual Firm R0hne** model: an
agentic, data-processing-only org where every role (product, comms, marketing)
is a panel agent and offerings move through the pipeline
(`idea→debate→prototype→staged→launched`). "Launched" is ALWAYS Laura-gated.
Clearly labelled "VIRTUAL FIRM (agentic, data-processing only)" — NO real
company is replaced, NO physical product is built.

**Files:**
- Modify: `factory/daily_spawn.py` — read `HITL_SECOND_REVIEWER`; log when
  both Laura-flag AND second-reviewer present.
- Create: `factory/virtual_firm.py` — pipeline orchestrator: takes a lead,
  routes to debate (Task 2), advances `PIPELINE` stage, stages for Laura.
- Test: `tests/test_governance.py` (assert virtual-firm output carries
  VIRTUAL-FIRM label; assert `staged→launched` requires Laura flag).

**Step 1 (test):** virtual-firm output labelled VIRTUAL-FIRM; spawn still
requires Laura flag. **Step 2:** FAIL. **Step 3:** implement. **Step 4:** PASS.
**Step 5:** commit `feat: HITL second-reviewer slot + Virtual Firm R0hne pipeline`.

---

### Task 5: Observatory UI surface (HTML, not just JSON)

**Objective:** A calm Palantir-grade `/observatory` HTML page showing center
status (healthy/degraded/0-status), debate log, lead counts, spawn_candidates
— so Simeon + Laura can WATCH the orchestra without grepping state.json.

**Files:**
- Modify: `factory/runtime.py` `observatory` — add `GET` HTML branch (keep
  JSON for `Accept: application/json`).
- Test: `tests/test_observatory_ui.py` (assert HTML contains status badges).

**Step 1 (test):** GET `/observatory` returns HTML with a status badge.
**Step 2:** FAIL. **Step 3:** implement calm grid (reuse index CSS tokens).
**Step 4:** PASS. **Step 5:** commit `feat: observatory HTML watch-page`.

---

## Files likely to change

- `factory/runtime.py` (status FSM, debate handler, leads, observatory HTML)
- `factory/synthesis.py` (debate context reuses `propagate_tensions`)
- `factory/daily_spawn.py` (second-reviewer gate)
- `factory/demo_firm.py` (NEW — simulation only)
- `factory/catalog.py` (no schema change; reads CENTER_NETWORK)
- `tests/` (NEW — pytest scaffold + 5 test modules)
- `pytest.ini` (NEW)
- `SESSION-LOG-2026-07-17.md` (append plan acceptance + HITL sign-off)

## Tests / validation

- `pytest -q` must pass; target ≥80% on new code (AGENTS.md).
- Live check after deploy (browser, per Simeon's "verified before continuing"):
  `/health`, `/observatory` (HTML + JSON), `/api/center/debate` with a real
  center key returns run_id, a forced engine error yields `degraded` status
  and 200 response.

## Risks, tradeoffs, open questions

- **R1 (honest):** "Apple replaced by agents" is NOT built — only a labelled
  `demo-firm` simulation. Claiming otherwise would be gaslighting.
- **R2:** Status FSM is graceful degradation, not magic self-healing. We say
  "reduced mode", never "healed itself".
- **R3:** Leads are only as good as real traffic. With 19 sessions today,
  leads are sparse — that's honest, not padded.
- **R4:** Laura MCP offline → spawning/money paths stay human-gated via the
  in-person HITL; code never self-approves a spawn.
- **OQ1:** Should `0-status` auto-recover on engine return, or require a human
  "resume"? (Recommend: auto-recover to `healthy` on first successful call,
  log it — no human needed for recovery, only for spawning/money.)
- **OQ2:** Does the second reviewer slot need an actual identity now, or is the
  env var + log enough until Laura + Simeon nominate one?
- **OQ1 (DECIDED):** 0-status auto-recovers to `healthy` on first successful
  engine call; logged, NO human needed for recovery — only spawn/money stay
  gated.
- **OQ2 (DECIDED):** `HITL_SECOND_REVIEWER` env var + log sufficient for now;
  Simeon/Laura nominate a real person later.
- **OQ3 (DECIDED):** Debate quorum = adjacent centers first; firm-wide convener
  added later behind a flag.
- **OQ4 (DECIDED):** Virtual Firm R0hne framing confirmed (agentic,
  data-processing-only, our own autonomous org, NOT a real company
  replacement; "Apple" was a parable for large-firm funnels/pipelines
  MVP→production). No physical product, no real-company takeover.
- **GO:** Simeon + Laura approved execution 2026-07-17T10:25:06Z.

## Execution handoff

Plan complete and saved. Ready to execute using `delegate_task` — I'll dispatch
a fresh subagent per task with two-stage review (spec compliance then code
quality). **No execution until Simeon + Laura say go.**
