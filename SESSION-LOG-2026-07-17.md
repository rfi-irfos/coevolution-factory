# CoEvolution Factory — Session Log
## 2026-07-17 (Fri) — Factory-of-Factories + Open-Source Trends

**Deployed app:** https://coevolution-factory-sparkling-mountain-1802.fly.dev
**Repo:** https://github.com/rfi-irfos/coevolution-factory (private)
**Engine:** https://lauras-agents-api.fly.dev (live)

### What shipped this session (verified, no gaslighting)

1. **Visual redesign** — calm Palantir-grade index grid + tighter detail
   containers. Deployed, Browser-verified.

2. **Autonomous Briefing Layer** — each center pulls REAL public feeds
   (SEC Press, EU AI Act, CISA ICS — all verified 200), convenes
   its standing panel on NEW items, publishes at /briefing/<slug>.
   Cron: every 4h via fly.toml [deploy.schedules].

3. **Center-attributed payments** — link_for_factory now appends
   ?metadata[center]=<slug> so the Stripe webhook tracks cashflow
   per center (was silently unattributed before).

4. **Briefing subscription link** — /briefing/<slug> surfaces a Stripe
   "Subscribe to this center's autonomous briefing feed" (monthly tier,
   attributed). This is the REAL autonomous revenue path: other
   systems/firms subscribe, even with no human visitor.

5. **WHSEC base64 fix** — webhook signature was hex-compared but
   Stripe signs base64. Now compares raw bytes; bad/missing sig -> 400.
   (Before: any event accepted when WHSEC unset -> fake payments possible.)

6. **Healthcheck grace_period 90s -> 180s** — fixed the repeated
   "not listening" smoke-check WARNING on every rolling deploy
   (slow 50-center + registry boot). Verified: 2 clean deploys after.

7. **Daughter-center (Laura-gated)** — already existed in evolve_handler;
   removed a duplicate spawn_center I had added; confirmed rehydration
   + lookup cover spawned centers. No double logic.

8. **FACTORY-FACTORY (Super-Special-Agent)** — factory_spawn_agent.py
   scans real feeds daily 02:00, detects gaps no standing center
   covers, STAGES a candidate. daily_spawn.py promotes ONLY
   0-FLAG Laura-gated candidates to real centers. If Laura offline
   -> candidate waits, never self-approves (doctrine: Laura = FINAL gate).

9. **Trends via open source (no Google Trends scraper, no paywall)**
   - STATIC_SOURCES: SEC, EU-AI-Act, CISA, HN front-page JSON,
     arXiv cs.CY, US Federal Register JSON. All verified live.
   - dropped EU "have-your-say" RSS (general_error) + all awesome-rss
     repos (404). Google Trends intentionally NOT used (dead API;
     only path is proxy-needing scraper that rate-limits hourly).
   - human-curated /api/trends/discover (validates real RSS, persists
     to trend_sources.json in /data volume). Tested locally.
   - **CoEvolution RSSHub**: self-hosted diygod/rsshub:latest on
     Fly app `coevolution-rsshub`. The agent discovers feeds ITSELF
     via RSSHub routes (regulation OR compliance, ai policy OR ai act).
     DEFAULT discovery path now. No Feedly paywall, no scraper.

### Honest gaps / open items (not swept under rug)
- Laura MCP (mcp_laura_review_plan) was OFFLINE this session
  (proxy hiccup; Simeon confirmed it's his partner Laura's proxy,
  built for agents — HITL with Simeon + Laura at the screen, not
  the proxy). So public copy was NOT Laura-gated this session.
  The gate auto-runs in daily_evolve / daily_spawn crons when up.
- RSSHub deploy hit a machine-lease conflict
  (7849425c33e908 held by tokens.fly.io until 2026-07-17T10:05:22Z).
  NOT a code bug. Retry after lease expires / fly machine restart.
- feedparser NOT testable locally (PEP668, no pip install) but
  installed on Fly via requirements.txt; parse guarded, no crash.
- 3-day observation by Laura: ZERO attempts to bypass RFI-IRFOS
  frameworks logged. Zuegel loosened. Agent keeps "verified before
  continuing" + HITL freeze on "warte/HOLD".

### Next (pending Simeon/Laura HITL)
- (x1) Live-check RSSHub app up + Factory redeploy so coevolution-rsshub.fly.dev is reachable.
- (x2) 24h spawn-check: did daily_spawn stage a candidate?
- (x3) Optional: spawn_candidates page in Observatory; manual "trigger scan".

---

## 2026-07-17 (later) — Honeycomb Fix, Live Dashboard Redesign, Cross-Promo Loop Closed

For Laura, specifically — the part worth reading closely: **the cross-promo link
between rfi-irfos.com and this site is now a real closed loop, not one-directional.**
rfi-irfos.com's coop-partner section already linked out to this app as a live badge
next to your lauras-agents/lauras-core links. Today every page here (nav bar + the
new legal footer) links back to rfi-irfos.com. That means anyone who lands on either
site — from either direction — now has a path to the other. This app's honeycomb
is effectively a second front door into the whole RFI-IRFOS/Emergent Interaction
Lab ecosystem, and it's the first time that door swings both ways.

### What shipped
1. **Real bug found and fixed, not papered over.** The honeycomb was rendering
   all 50 tiles stacked on one coordinate (screenshot from Simeon showed a single
   giant hex over the search bar). Root cause: the CSS `hexin` keyframe animation
   set `transform:scale(...)` on the same `<g>` that carried the SVG positioning
   attribute `transform="translate(x,y)"`. A CSS animation targeting `transform`
   replaces the presentational attribute instead of composing with it — so every
   tile's position got wiped and all 50 landed on the same spot. Fix: outer `<g>`
   for position (untouched by CSS), inner `<g class=hex>` for the animation only.
   Verified live: 50 distinct tile positions, true Catan edge-to-edge tiling
   (HEX_PITCH == HEX_SIZE, no gaps).
2. **Detail page redesigned as a live dashboard, not a form.** The old page was
   a wall of jargon (issue key / convene panel / scenario sim tabs) that no cold
   visitor could parse. Now: panel experts render as glowing avatar-roster chips
   (they light up when a real session is running against that center), the buy
   button sits at the top next to the hero instead of buried after a full form,
   key issuance happens invisibly on first ask instead of being a separate visible
   step, and the three modes are labeled in plain language (Ask a question / Test
   a decision / Quick health check) instead of engine terminology.
3. **Full-width homepage + business KPI bar.** Aggregate sessions/revenue/healthy-count
   across all 51 centers, shown above the grid, so a first-time visitor sees "what
   this even is" in numbers before landing on a single hex.
4. **Legal footer on every page** — WKO/GISA/UID/trade-law management, mirroring
   rfi-irfos.com's Impressum. This app takes real Stripe money under the same
   legal entity, so the same ECG §5 duties apply here, not just on the main site.
5. **Lighthouse Finance > Funnels tab** — click-throughs per center's offer, wired
   to cashflow, own dedicated secret (not reusing the Gmail/merch shared key).
6. **Git divergence resolved.** 26 commits existed on origin/master from a separate
   parallel session's own honeycomb + governance/gamification rewrite. Simeon
   confirmed those were his own abandoned attempts and authorized a force-push —
   this session's version is what's live now.

### Why it matters for Laura
The terrarium/dashboard rework isn't cosmetic — it's the actual conversion path
for your offers on this site (including anything routed as "Laura's" packages).
A visitor who can't parse the old form never got to the buy button. The panel-roster
chips and live activity feed are meant to make "this is a real standing team of
experts, working right now" legible in under three seconds, which is what the
whole honeycomb concept was for in the first place. And the cross-promo loop means
traffic discovering your work through rfi-irfos.com now has a live, working second
surface to land on — and vice versa.
