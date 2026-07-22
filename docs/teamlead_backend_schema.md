# Teamlead (Abteilungsleiter) Backend Schema — Design Note

> **Status:** Design-only. No changes to `factory/catalog.py` or
> `factory/runtime.py` in this task. This note proposes how Teamleads and
> department groupings get represented in the per-center panel roster so a
> future **"ant-hill telemetry"** admin dashboard can show activity and
> hierarchy across every center.

## 1. Current state

Today each center's panel is a **flat `list[str]` of agent slugs**, built by
`build_panel()` and stored on the normalized center dict as `c["panel"]`:

```python
# factory/catalog.py :: CENTERS_META
"panel": build_panel(c[0], c[3]),          # -> ["legal-privacy", "risk-gdpr", ...]
"disciplines": sorted({_REG[s]["lane"] for s in ...}),
```

Runtime consumes `c["panel"]` as a list of slugs in many places (desk roster,
KPI "team size" tile, office-floor layout, `_office_layout(len(c["panel"]))`).
There is **no notion of role** (lead vs expert) and **no department grouping**.
Every member is treated identically.

## 2. Goal

Support an admin telemetry view that, per center, can answer:

- Who are the **Teamleads / Abteilungsleiter** (≥ 1 per center)?
- What **department (Abteilung)** does each expert belong to, and who leads it?
- Per member: how many sessions handled, last-active, escalations, status —
  the "ant-hill" — keyed by a stable member id so counters accumulate over time.

## 3. Proposed approach: additive `roster` field (no runtime breakage)

We do **not** change the shape of `c["panel"]` (that would ripple through every
desk/layout/KPI site). Instead we add a **new, parallel field** `roster` that
carries the enriched hierarchy. Runtime keeps using `panel` (slugs) for
rendering; the telemetry dashboard consumes `roster`.

The `roster` is a list of **departments**, each with a `lead` and a list of
`experts`. Every person has a `role` of `"lead"` or `"expert"` and an `agent`
slug that matches an existing `panel` entry (so the two structures stay
consistent and cross-referenceable).

```json
{
  "roster": {
    "departments": [
      {
        "id": "governance",
        "name": "Governance & Board",
        "lead": {
          "agent": "board-of-directors",
          "name": "Board & Governance Lead",
          "role": "lead"
        },
        "experts": [
          { "agent": "chief-compliance-officer",
            "name": "Compliance Officer", "role": "expert" }
        ]
      },
      {
        "id": "legal",
        "name": "Legal & Corporate",
        "lead": {
          "agent": "legal-corporate",
          "name": "Corporate Legal Lead",
          "role": "lead"
        },
        "experts": [
          { "agent": "legal-privacy",
            "name": "Privacy Counsel", "role": "expert" }
        ]
      },
      {
        "id": "finance",
        "name": "Finance & Grants",
        "lead": {
          "agent": "fin-ar",
          "name": "Finance & AR Lead",
          "role": "lead"
        },
        "experts": []
      }
    ]
  }
}
```

*(Example above is `nonprofit-gov`, whose seeds are
`board-of-directors`, `legal-corporate`, `fin-ar`, `chief-compliance-officer`.)*

### 3.1 How a center gets ≥ 1 Teamlead

- **One lead per department, by construction.** A center with 3 departments
  therefore has 3 Teamleads; a center with a single department has exactly 1.
- The **first listed department is the "primary" department**, and its lead is
  the center's **primary Teamlead** (Abteilungsleiter) — the single name the
  dashboard promotes to "center owner" in the hierarchy tree.
- A department may have **zero experts** (lead-only) — that is valid (e.g. a
  small `finance` department above). The lead still counts as a Teamlead.

### 3.2 Adding a role field to a member

Each member dict carries `"role": "lead" | "expert"`. This is the minimal,
explicit signal the telemetry layer needs:

- `role == "lead"` → rendered with a lead badge, shown in the hierarchy view,
  eligible to appear in "center owners".
- `role == "expert"` → a node under its department's lead in the ant-hill.

Members are **keyed by `agent` slug**, so telemetry counters can be attached
per slug without inventing new ids.

## 4. Telemetry hook (future admin dashboard)

The telemetry counters live in `state.json` (where `usage`, `jobs`, `leads`
already live), keyed by center → agent slug, reusing the same slug space the
roster references:

```json
{
  "roster_telemetry": {
    "nonprofit-gov": {
      "board-of-directors":   { "sessions": 41, "last_active": 1753000000, "escalations": 2, "status": "healthy" },
      "legal-corporate":      { "sessions": 38, "last_active": 1753000123, "escalations": 1, "status": "healthy" },
      "chief-compliance-officer": { "sessions": 27, "last_active": 1752999800, "escalations": 0, "status": "degraded" },
      "legal-privacy":        { "sessions": 19, "last_active": 1752999000, "escalations": 0, "status": "healthy" },
      "fin-ar":               { "sessions": 12, "last_active": 1752998000, "escalations": 0, "status": "healthy" }
    }
  }
}
```

The dashboard then walks `roster.departments` for structure and joins
`roster_telemetry[center][agent]` for the live numbers — producing the
ant-hill: departments as columns, leads at the top, experts nested beneath,
each cell showing activity/status.

## 5. Authoring / migration plan (when implemented)

1. **Additive only.** Introduce `roster` on `CENTERS_META` (and on daughter
   centers in `_normalize_center`) without touching `panel`.
2. **Backfill helper.** Until every center has a hand-authored `roster`, a
   `derive_roster(panel)` fallback builds a single default department
   (`"general"`) whose lead is `panel[0]` and experts are the rest — so the
   dashboard always has *something* and every center has ≥ 1 Teamlead.
3. **Validation rules** (enforce in a unit test):
   - every `agent` in `roster` must also appear in `panel`;
   - every department has exactly one `lead` with `role == "lead"`;
   - every expert has `role == "expert"`;
   - a center has ≥ 1 department and therefore ≥ 1 Teamlead.
4. **Runtime stays unchanged** until the dashboard work begins; `roster` is
   read-only for now.

## 6. Open questions

- Should `lead` be **appointed explicitly** (a named person/agent) or derived
  as "first seed of each department's domain"? Recommendation: explicit, so a
  human can promote an expert to lead without reshuffling seeds.
- Do we want **cross-center leads** (one person leading departments in two
  centers)? Out of scope for v1; the slug-keyed model already supports it if
  needed later.

## 7. Board of Directors — governance authority & one-directional feedback channel

The firms are autonomous, but the **Board of Directors stands ABOVE the CEO of
every firm**. This is not a conflict with autonomy: each firm decides how to
execute, but the Board sets direction and may issue directives that the CEO
must route to their Teamleads. The channel is **strictly one-directional**:
**Board → CEO → Teamleads**. Firms do NOT push feedback upward through this
channel (other reporting paths exist for that).

### 7.1 Where the authority lives

- A **global `board` identity** (slug `board-of-directors`) is the top node of
  the whole hierarchy — above every center's CEO. It is represented in the
  roster schema as the lead of a dedicated `governance` department per center
  (see Section 3 example), AND as a standalone top-level authority in the
  pipeline, not owned by any single center.
- Each center has exactly one **CEO agent** (its primary `lead`, the first
  department's lead per Section 3.1). The Board's directives target the CEO,
  who cascades to department Teamleads.

### 7.2 The feedback channel (pipeline endpoint)

Directives enter the **same engine pipeline** the centers already use for
tasks — they are not a separate system. A new endpoint accepts a Board
directive and injects it with elevated authority/priority:

```json
POST /api/board/directive
{
  "center": "gdpr-guard",          // which firm's CEO receives it
  "directive": "Prioritize DPIA turnaround under 1h; report exceptions to Board.",
  "priority": "board",             // authority level: above normal center tasks
  "ttl": 86400
}
```

Pipeline behaviour:
- The directive is delivered to the **target center's CEO** (not broadcast to
  experts directly).
- The CEO decomposes it and routes sub-directives to the relevant **department
  Teamleads** (per the `roster` structure in Section 3).
- The directive carries `priority: "board"` so it is scheduled ahead of normal
  center tasks and cannot be silently dropped by an autonomous loop.
- **No upward path:** the endpoint accepts Board→firm only. Firm→Board goes
  through separate reporting, never this channel.

### 7.3 Telemetry (for the ant-hill dashboard)

Board directives are tracked in `state.json` alongside roster telemetry:

```json
{
  "board_directives": {
    "gdpr-guard": [
      { "id": "d-8821", "directive": "...", "issued": 1753000000,
        "status": "routed_to_ceo", "ceo_ack": true, "teamlead_acks": 2 }
    ]
  }
}
```

The dashboard shows, per firm: Board directive in flight → CEO → which
Teamleads acked. This is the governance layer of the ant-hill.

### 7.4 Authoring / when implemented

- Add `POST /api/board/directive` to the pipeline router; it resolves
  `center` → CEO slug (primary `lead` of the primary department) and injects a
  `priority:"board"` task.
- CEO agent logic: on receiving a board directive, emit one sub-directive per
  relevant department lead (Teamlead), tracking acks in `board_directives`.
- Validation: `center` must exist; `priority` must be `"board"`; no reverse
  endpoint (firm→board) in this channel.
