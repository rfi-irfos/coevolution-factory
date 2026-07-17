# Autonomous AI Company — Build Plan

> Source assets: `rfi-irfos/lauras-agents` (private, **LIVE model-backed engine — this is the product**) + `rfi-irfos/lauras-agents-public` (concept/schaufenster) + `rfi-irfos/call-laura` (free **deterministic teaser only**, live on crates.io + laura-api.fly.dev).
> Doctrine: Laura = final ship gate. Everything user-facing runs through `mcp_laura_review_plan` before publish.
> IP rule: the 292 prompts are the product. Public = the contract + free teaser. Private = deployable Rust binary = the money-maker.
>
> **REALIGNMENT (2026-07-16):** the COMPANY is built on the *real* engine, not the deterministic free tool. `call-laura` is only the top-of-funnel teaser. Every daughter is a *real, licensed, metered business* over the live 292-agent pipeline. "Autonomous" = operational autonomy (engine + billing run without a human); incorporation, banking, and the Laura gate stay human-owned.

---

## 0. What we actually own (the moat)

This is not "an LLM wrapper." It is a **licensable, entitlement-gated, metacognitive multi-agent review engine**:

- **15 hand-authored core agents** (security, legal, privacy, AI-safety, exec risk…) — each locked in its own lane, told to quote verbatim or say nothing.
- **292 data-driven function-agents** generated from a full org map (every C-suite, every VP lane: legal-ip, be-payments, risk-gdpr, cfo, mkt-growth-seo…). Each carries frameworks + `feeds_into` edges so a flow like "launch an AI feature" becomes a directed graph across the team.
- **Entitlement model at the network boundary** — `LAURA_AGENTS_KEYS=key1:slug,slug;key2:*`. A single-agent licensee's key *cannot* reach other agents. This is the productization primitive that makes per-agent / per-bundle / full-pipeline licensing real, not a price list.
- **Metacognition** — after each pass every agent audits its own output, may rewrite its own prompt (version-bumped, append-only trace), and stages skill proposals for human review only. This is the EU AI Act transparency requirement made operational, and it's a defensible differentiator vs. black-box competitors.
- **Mission Control turntable** — 30 "locomotives" run one-at-a-time through a document under a 2-view ternary context gate, with a Watchtower BI dashboard showing live state + HITL annotation.
- **`call-laura`** — free, deterministic, local, live on crates.io + Fly. Same 15-role taxonomy, pattern-matching instead of model calls. Zero cost, fully inspectable. It is the honest top-of-funnel.

**Why this beats a single smart model:** one model asked to "find anything wrong" has no incentive to stay in lane and blends a security flaw into a legal nitpick into a wording complaint. Our agents run in parallel, each only talks about its lane, and when two independently flag the same verbatim line that's a real signal — not a mood.

---

## 1. Market (hard numbers)

- AI-agent market: **$7.6B (2025) → $10.9B (2026) → $182.9B (2033)**, CAGR **49.6%** (Grand View Research).
- Legal AI comps: **Harvey** — $300M ARR (May 2026), $8B valuation, $160M Series F led by a16z. **Norm AI** — $1.2B valuation, $120M Series (agentic compliance).
- The wedge: Harvey sells *to* legal teams. Nobody sells a **licensed, whitebox, entitlement-gated multi-agent review engine** you embed into *your* pipeline, per-agent, with EU-AI-Act-grade transparency. That is our lane.
- Adjacent comps: Vanta / Secureframe (continuous compliance), but those monitor controls — they don't run a 292-agent org-graph review over your documents. Norm AI does agentic compliance but is a closed product, not a licensable engine.

---

## 2. The company model: one parent, N autonomous daughter-startups

The parent is the **engine + the platform + the brand**. Each daughter is a vertical product built *on the same engine*, spun out with its own pricing page and its own revenue line, so the parent funds several independent AI startups from one tech base.

```
            ┌─────────────────────────────────────────┐
            │  PARENT — RFI-IRFOS Licensable AI Engine  │
            │  (Rust/Axum API · 15+292 agents · metacog)│
            └───────────────┬───────────────────────────┘
   ┌──────────────┬─────────┴──────────┬───────────────┬──────────────┐
 Daughter A    Daughter B    Daughter C      Daughter D     Daughter E
 ComplianceAI  DocuReview    LaunchGuard      GRC-Agent     AuditWatch
 (per-doc)     (per-run)     (pre-launch)     (continuous)  (SOC2/ISO)
   own price    own price      own price        own price     own price
   own rev line  own rev line   own rev line     own rev line  own rev line
```

Each daughter = a focused landing page + a metered API + a Stripe/Polar product. The parent owns the engine; daughters pay the parent per inference (internal transfer) and keep margin. This is how "one tech → several funded startups" works mechanically.

---

## 3. The product (what ships first)

**Flagship: an autonomous document/compliance review API + dashboard.**
- Input: a document, a regulatory trigger (GDPR / EU AI Act / SOX / HIPAA / IP), or a "launch this feature" intent.
- Engine: routes to the entitled agent subset, runs them in parallel, returns verbatim-cited findings with `blocker|flag|note` severity + a whitebox metacog transparency roll-up.
- Output: human-facing report (not actions), HITL annotation, export to JSON/CSV/MD.
- Free tier: `call-laura` (deterministic, no key). Paid: the live NIM-backed pipeline, per-agent licensing.

**Why this is the right first product:** it is *already built* (the private repo runs; call-laura is live). The only net-new work is (a) the public landing page, (b) a billing/metering wrapper, (c) a licensee onboarding flow. Lowest time-to-revenue of any option.

---

## 4. Autonomous revenue architecture (the "totally autonomous" part)

The product is autonomous by design (the engine runs without humans in the loop, only HITL on skill-install). The *business* is made autonomous by wiring:

1. **Metered billing** — every API call emits a usage event. Use **Polar.sh** (Merchant of Record: handles global VAT/tax, payouts, no Stripe tax headache) or **Stripe Billing** with usage records. Plan: free tier (call-laura) → per-run credits → per-agent monthly license → full-pipeline enterprise.
2. **Self-serve onboarding** — signup → key issuance → entitlement assignment → first run, all via the API + a small React/HTMX console. No sales call required to start.
3. **Autonomous marketing site** — the landing page itself is the sales motion: clear value, live demo (call-laura), pricing, signup. Content can be refreshed by the marketing function-agents (mkt-content-blog, mkt-growth-seo) on a schedule.
4. **Autonomous ops** — Watchtower dashboard already shows live runs, revenue can be piped in. The engine self-improves (metacog) without human intervention on prompts.
5. **Reinvest loop** — margin from daughters funds the next daughter's landing page + metering. Each daughter is a template: clone the billing wrapper, point at a new agent subset, ship.

**Honest caveat:** "totally autonomous" revenue still needs (a) a payment-processor account with real banking behind it — that's you, not the agent; (b) initial traffic/go-to-market, which the marketing agents can run but won't invent out of nothing; (c) Laura gate on any public copy. The autonomy is in *operation*, not in *incorporation*.

---

## 5. Daughter-startup portfolio (concrete verticals off the engine)

| Daughter | Built from engine agents | Customer | Pricing shape |
|---|---|---|---|
| **ComplianceGuard** | risk-gdpr, risk-sox, risk-hipaa, legal-compliance, legal-privacy | Regulated SMBs/scale-ups | per-doc + monthly |
| **LaunchLens** | ai-safety-governance, legal-ip, sece-ng-appsec, chief-ai-officer | Product teams shipping AI features | per-launch audit |
| **DocuTrust** | legal-corporate, legal-employment, legal-litigation, docs-tech-writers | Legal ops / contracts | per-run credits |
| **BoardEye** | ceo, cfo, board-of-directors, chief-risk-officer, corpdev-diligence | Founders / VCs pre-diligence | per-report sub |
| **GRC-Auto** | risk-enterprise, risk-ethics, quality-iso, gov-compliance | ISO/SOC2 candidates | continuous monthly |

Each is the *same* binary with a different `LAURA_AGENTS_KEYS` entitlement + a different landing page. That's the whole trick: one engine, many priced fronts.

---

## 6. Funding path (use the daughters to raise)

- **Now → 90 days:** ship parent landing + ComplianceGuard daughter + metering. Get 10–50 design-partner runs. This is the traction artifact.
- **Seed raise:** lead with the moat (licensable whitebox engine + metacog transparency + entitlement model) and the Harvey/Norm comps. Ask: €1.5–3M to staff the billing/console + 2 more daughters. The autonomous-revenue architecture is the "why now / why defensible" story.
- **Series A:** after 3 daughters at combined €Xk MRR, raise on the "one engine → portfolio of AI startups" thesis. Each daughter is a line item with its own unit economics.
- **Non-dilutive:** the engine is EU-clean and ternary-native — eligible for EU AI/chip grants (e.g. Austria/EC AI innovation calls). Pursue in parallel; it de-risks the raise.

---

## 7. 90-day build plan (concrete)

- **Wk 1–2:** Landing page (this repo) + run public copy through Laura gate. Stand up Polar or Stripe sandbox.
- **Wk 3–4:** Billing/metering wrapper around `lauras-agents-api`: signup → key → entitlement → usage events. Wire call-laura as the free teaser on the site (live embed or link).
- **Wk 5–6:** ComplianceGuard daughter: entitlement config + pricing page + first design partners (use existing Graz/RFI network + legal ops communities).
- **Wk 7–10:** Watchtower revenue view + autonomous content (mkt agents) + LaunchLens daughter.
- **Wk 11–12:** Traction pack (run samples, MRR, deck) → warm investor outreach. Document everything to session_log + RuVector.

---

## 8. Open decisions for Simeon (need your call)

1. **Parent/product name** — `lauras-agents` is taken as the engine brand; the *company* needs a name (e.g. "Laura Systems", "CoEvolution AI", "Ternary Labs"). 
2. **Billing provider** — Polar (MoR, zero tax pain, dev-first) vs Stripe Billing (more control, you do tax). My rec: Polar to stay autonomous.
3. **Deploy target** — Fly.io (already used for call-laura + lighthouse) keeps it in-house and EU-clean. Keep it.
4. **First daughter** — my rec: ComplianceGuard (closest to built engine + hottest comp = Norm AI).
5. **Legal entity** — billing needs a real registered entity + bank. RFI-IRFOS (ZVR 1015608684) can be the parent, or a new GmbH. Your call.

---

## 9. Guardrails (non-negotiable)

- Laura gate on ALL public copy (laura-gate skill) before any push/publish.
- 292 prompts stay private. Public repo = concept + free tool only.
- Never auto-send email / never push without gate (doctrine).
- "Autonomous" = operational autonomy. Incorporation, banking, and the Laura gate stay human-owned.
