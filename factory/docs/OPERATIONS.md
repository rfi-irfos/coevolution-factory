# CoEvolution Factory — Operations Runbook

Autonomous 50+ center system. This is the live operational reference for the
Virtual Firm R0hne pipeline, the red-team hardening, and the reversible
self-launch. Read this before touching gates or secrets.

App: https://coevolution-factory-sparkling-mountain-1802.fly.dev
Repo: https://github.com/rfi-irfos/coevolution-factory (private)
Engine: https://lauras-agents-api.fly.dev (Laura's agent API)

---

## 1. The Virtual Firm R0hne pipeline

A REAL inbound lead (from a visitor panel session or an inter-center debate)
flows through an offering pipeline:

```
idea -> debate -> prototype -> staged -> launched
  ↑        ↑          ↑         ↑          ↑
real    resolved   evidence   READINESS   LAURA GATE #1
lead    debate     accrues    GATE        (daily_spawn)
                       │         │
                       │         └─ promote_prototype_to_staged(): only with a
                       │            resolved debate AND >= VF_STAGE_MIN_LEADS
                       │            real leads (default 3). Registers a
                       │            spawn_candidate (status='staged').
                       └─ route_lead_to_pipeline(): seeds at 'idea', advances
                          idea->debate->prototype on real debate evidence.
```

- **staged -> launched** is gated. Without Laura's clearance it never happens.
- All pipeline state lives in `state.json` under `pipeline`, `leads`,
  `debates`, `spawn_candidates`. No fabricated centers, no PII (leads are
  SHA-256-hashed question hashes only).

---

## 2. Reversible self-launch (the gates)

A staged Virtual Firm offering can LAUNCH ITSELF, but ONLY when EVERY gate
below is true. This is opt-in and reversible.

| Gate | Env var | Default | Meaning |
|------|---------|---------|---------|
| Auto-launch opt-in | `VF_AUTO_LAUNCH` | `0` (off) | Must be `1` to allow self-launch at all |
| HITL second reviewer | `HITL_SECOND_REVIEWER` | unset | A nominated human slot (e.g. `simeon-appointed`) |
| Laura gate #1 | `laura_pass` on candidate | `False` | Laura's deterministic review cleared it |

`launch_staged_offering(oid)` in `virtual_firm.py` checks all three. If any
is false it returns `{launched: False, reason}` and leaves the offering at
`staged`. **Without `laura_pass`, it NEVER launches — even with the other two
gates set. Laura is the final ship gate.**

Live env (set via `fly secrets set`):
- `VF_AUTO_LAUNCH=1`
- `HITL_SECOND_REVIEWER=simeon-appointed`

### Rollback

Every self-launch is reversible. Before promoting, the module snapshots the
pre-launch `CENTERS` keys into `state["rollback"][oid]`.

To reverse a launch:
```python
import virtual_firm as VF
result = VF.rollback_launch(oid)
# -> removes the promoted center from CENTERS/CENTER_SLUGS/CENTER_NETWORK,
#    drops the offering back to 'staged'.
```

Or via the running app (operator key required):
```
POST /api/vf/rollback  body {"offering_id": "<oid>"}
```
(Not yet wired as an HTTP route — call `rollback_launch` directly or add the
route; the function is the source of truth.)

Find the `oid` of a launched offering in `/observatory` (Virtual Firm card ->
last_offering) or in `state.json` under `pipeline` where `stage == "launched"`.

---

## 3. Red-team hardening (rfi-irfos-infra-hardening doctrine)

All verified offline + live. No known open findings.

- **Reflected XSS**: index `?q=` search query and `center_page` cached JSON are
  `html.escape()`'d. Verified live: `?q=<script>` returns escaped text.
- **Auth gate**: every mutating operator route requires a center key
  (`require_operator`). Without a key -> 401. Verified live.
- **Spawn containment**: `spawn_session` rejects missing text, fabricated
  agents (not in registry), and unknown centers (404). Duplicate daughter
  slugs are blocked in the evolve path.
- **No-PII leads**: `add_lead` stores only a SHA-256 hash of the incoming
  text. Raw visitor text is never persisted.
- **Resilience**: a `degraded` / `0-status` center still serves HTTP 200 with
  an honest "reduced mode" banner + last cached synthesis. It never returns
  500 or fabricates a fresh verdict.
- **CORS**: explicit, strict. No `Access-Control-Allow-Origin: *`. Cross-origin
  requests get no ACAO header. Verified live.
- **Rate-limit**: operator routes are bounded at `VF_RATE_MAX` (default 20)
  hits per `VF_RATE_WINDOW` (default 60s) per (ip, route) -> 429 + Retry-After.
  Stops a leaked key from burning engine budget or brute-forcing.

Tune without code changes:
- `VF_RATE_MAX`, `VF_RATE_WINDOW` — rate-limit shape.
- `VF_STAGE_MIN_LEADS` — how many real leads a prototype needs before staging.
- `VF_AUTO_LAUNCH` — kill switch for self-launch (set to `0`).

---

## 4. Daily autonomous loop (cron)

- `coevolution-daily-evolve` (02:00 UTC): scans trends, stages spawn
  candidates, runs Laura's gate on staged candidates.
- `coevolution-daily-debate` (03:00 UTC): runs inter-center debates, advances
  related offerings, surfaces resolutions in `/observatory`.

These are the autonomous drivers. They do NOT need an operator key — they run
on the scheduled service account. A real lead that reaches `staged` with
`laura_pass=True` will self-launch on the next `orchestrate()` call (driven by
any lead routing), reversibly.

---

## 5. Emergency kill switches

| Want | Do |
|------|-----|
| Stop all self-launches | `fly secrets set VF_AUTO_LAUNCH=0` (restarts app) |
| Remove second-reviewer requirement | `fly secrets unset HITL_SECOND_REVIEWER` |
| Reverse a launch | `VF.rollback_launch(oid)` (see §2) |
| Full app rollback | `fly releases rollback` to previous deployment |

---

## 6. Tests

`pytest tests/` — 37 passed. Covers: state, resilience/status-FSM, debate,
CRM leads (no-PII), governance/HITL, observatory UI, red-team (5 classes),
pipeline loop, red-team hardening (CORS + rate-limit), reversible self-launch.

Run locally: `FT_STATE_DIR=/tmp/ft pytest tests/ -v`
