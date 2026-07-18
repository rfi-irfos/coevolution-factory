# CoEvolution Factory

## Human rights are not subject to negotiation.


Autonomous, revenue-generating AI product line built on the private
**lauras-agents** engine (RFI-IRFOS). One parent engine + one generic
multi-tenant runtime + a catalog of 50 standing, interdisciplinary
**centers**, each solving a distinct, crisis-resistant compliance / risk
problem.

- **Live app:** https://coevolution-factory-sparkling-mountain-1802.fly.dev/
- **Engine:** https://lauras-agents-api.fly.dev (the real 292-agent pipeline)
- **Cashflow only:** the Observatory tracks per-center sessions + EUR. No
  human in the money path.

> **Deutsch:** Autonomous, autonomiegetriebene KI-Produktlinie über der
> privaten lauras-agents-Engine (RFI-IRFOS). 50 stehende,
> interdisziplinäre "Center", jedes löst ein eigenes, krisenfestes
> Compliance-/Risk-Problem. Wir tracken nur den Cashflow.

---

## What it is

50 distinct **centers** (not document processors). Each is a standing body
of experts that convenes around ONE durable problem — GDPR, AI Act, SOX,
HIPAA, supply-chain risk, bias audit, … — drawn from every relevant
discipline in the real 292-agent registry (Legal / Risk / AI-Safety /
Finance / Ops / Security / Exec).

Each center can:
- **Convene panel** — review a visitor's question through the live engine.
- **Scenario sim** — run a proposed action ("what if we ship X?") through
  the panel before it happens.
- **Standing check** — a continuous posture snapshot of the center's
  exposure.

Centers re-synthesize across a real **adjacency graph** (derived from the
registry's `feeds_into` edges), so they are a network, not 50 silos.

Recursive self-improvement: a daily cron re-optimizes each center's panel
from real telemetry, **gated by Laura** (no self-approval).

---

## Architecture

```
factory/
  runtime.py        aiohttp app. Routes: /<slug> (center page),
                    /signup, /api/center*, /observatory, /network,
                    /evolve, /evolve/apply, /stripe/webhook
  catalog.py        50 CENTERS + panel expansion from the real registry.
                    CENTERS_META, CENTER_NETWORK, build_panel().
  evolve.py         recursive self-improvement (telemetry -> panel rewrite
                    -> live-test on engine -> propose). APPLY only via
                    /evolve/apply with a laura_pass token.
  daily_evolve.py   cron entrypoint: walks all centers, stages proposals,
                    carries each through mcp_laura_review_plan, applies the
                    0-FLAG ones.
  synthesis.py       local, deterministic cross-synthesis of the engine's
                    OWN findings (no extra LLM call, no fabrication).
  stripe_links.py    central RFI-IRFOS Stripe link pool + tier->link map.
  Dockerfile        python:3.12-slim; copies the registry into the image
                    so panels expand offline.
  fly.toml          app coevolution-factory-sparkling-mountain-1802,
                    region fra, /data volume mount.
  state.json         runtime state (keys, usage, jobs). LIVES ON THE
                    /data VOLUME, never committed. See .gitignore /
                    .dockerignore.
```

### Engine call
`call_engine()` POSTs `{text, agents, metadata}` to
`FT_ENGINE_URL/pool/team` with `Authorization: Bearer FT_ENGINE_KEY`.
The engine reviews agents **sequentially** (~15s each) → a 4-agent panel
takes ~30–60s. The runtime returns a `run_id` immediately and the
frontend polls `/api/center/result/{run_id}`.

### DEMO mode (honest degradation)
If `FT_ENGINE_KEY == "local"` AND the engine URL is remote, the service
degrades to **DEMO**: public surface stays up, but panel sessions return a
clear "engine key not configured" note instead of faking gated-engine
output. It never silently authorizes against or fabricates findings from
the real engine.

---

## Local setup

```bash
cd factory
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Demo (no engine key needed — runs in DEMO mode):
python runtime.py

# Live (needs the real engine key, injected as a Fly secret in prod):
export FT_ENGINE_URL=https://lauras-agents-api.fly.dev
export FT_ENGINE_KEY=<real engine key>      # set as Fly secret in prod
export FT_AGENT_REGISTRY=/abs/path/to/lauras-agents/crates/lauras-agents-registry/agents
python runtime.py
```

Visit http://localhost:8091/ . The index lists all 50 centers; each
`/<slug>` is a working center page.

---

## Deploy

```bash
cd factory
fly deploy --app coevolution-factory-sparkling-mountain-1802 -y
```

- `fly.toml` pins `primary_region = fra` and mounts the `factory_data`
  volume at `/data` (shared state across the 2 HA machines).
- `FT_ENGINE_KEY` is injected at runtime via `fly secrets set` — **never
  baked into the image.** The Dockerfile leaves it as `local` (DEMO).
- `.dockerignore` excludes `state.json`, `evolve_log.jsonl`, and
  `state.json.bak.*` so local state is never built into the image.

### Stripe webhook (one-time, manual)
In the Stripe dashboard → Developers → Webhooks → Add endpoint:
- URL: `https://coevolution-factory-sparkling-mountain-1802.fly.dev/stripe/webhook`
- Event: `checkout.session.completed`
- Optional: set `STRIPE_WHSEC` as a Fly secret for signature verification
  (`/stripe/webhook` enforces it when present).

---

## API (for the team)

| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/` | center index (search `?q=`) |
| GET | `/discover?q=` | JSON discovery |
| GET | `/<slug>` | public center page |
| POST | `/signup?center=<slug>` | issue entitlement key (needs email) |
| POST | `/api/center?center=<slug>` | convene panel (key + text) → `run_id` |
| GET | `/api/center/result/<run_id>` | poll synthesis |
| POST | `/api/center/scenario` | what-if sim |
| POST | `/api/center/healthcheck` | standing posture |
| POST | `/api/center/resolve` | cross-center tension propagation |
| POST | `/api/center/spawn` | spawn a gap team on demand |
| GET | `/observatory` | **cashflow only** (sessions + EUR) |
| GET | `/network` | adjacency graph |
| POST | `/evolve` | PROPOSE recursive panel change (staged) |
| POST | `/evolve/apply` | APPLY staged change (needs `laura_pass`) |
| POST | `/stripe/webhook` | real Stripe webhook |

All `/api/center*` routes require `Authorization: Bearer <key>` issued by
`/signup`.

---

## Recursion & the Laura gate

`/evolve` proposes; it does **not** apply. The daily cron
(`coevolution-daily-evolve`) walks every center, tests the candidate
panel on the live engine, then carries each proposal through
`mcp_laura_review_plan`. Only proposals with **0 FLAGs** get a
`laura_pass` token and are applied via `/evolve/apply`. A center may
**never self-approve.** This is doctrine, not a suggestion.

---

## Governance (READ BEFORE PUSHING)

This is a public-facing, money-handling system. Two hard rules:

1. **Laura = FINAL ship gate.** Any change to *public copy* (UI text,
   marketing, center descriptions) must pass `mcp_laura_review_plan`
   before deploy. Do not self-approve.
2. **No push without explicit OK.** The repo is private; PRs are reviewed
   by the RFI-IRFOS team before merge. Never force-push `main`.

### Honesty constraints (baked into the code)
- DEMO mode shows a clear "engine key not configured" note. It does not
  fake engine findings.
- Synthesis only aggregates the engine's *own* responses. It invents
  nothing.
- The Observatory shows cashflow only. No human sits in the money path.

---

## Repo layout

```
autonomous-ai-co/
  factory/            the 50-center runtime (this app)
  complianceguard/    earlier single-center prototype (reference)
  agents_registry/    copied real-agent registry (baked into image)
  README.md
```

State (`state.json`) is on the Fly `/data` volume and is git- + docker-
ignored. Clone, set up the venv, and you can run the whole thing locally
in DEMO mode without any secrets.
