# Honeycomb Tile Widget — Debug + Audit Plan

> **For Hermes:** This is a DEBUG/AUDIT plan (no implementation this turn). Inspect the landing honeycomb tile widget, list real defects, then hand off a fix plan.

**Goal:** Audit the landing-page honeycomb tile widget (`factory/runtime.py` `_tile` + `_firms_grid_body` + the `poll()` JS + `live_grid`) for correctness, performance, and visual-consistency defects, and produce a concrete fix plan.

**Scope (the widget):** The `.hex` tile — SVG `<path class=hexshape>` (rounded hex), `<foreignObject>` `.hexbody` (icon + name + LED + stats), the 10s `poll()` that patches `data-c`/stroke/LED/stats, and `/api/live-grid` (the data source). NOT the modal, NOT the ant-farm.

---

## Step 1: Read the widget surface (read-only)

**Files:**
- `factory/runtime.py` — `_firms_grid_body` (~3401), `_tile` (~3450), `HEX_POINTS`/`HEX_PATH`/`_hex_path` (~3204), `live_grid` (~1833), `_live_stats_for` (~605), the inline JS `poll()` (~3559), CSS `.hex*` (~3555).

**Actions:**
- Confirm `HEX_PATH` is a rounded `<path d="M…A…">` (corner=0.30) — DONE (arc radius 22.20 live).
- Confirm `_hex_icon` never returns empty (fallback to shield) — DONE (0 empty svgs live).
- Confirm `live_grid` returns `kind` — DONE (idle/discuss live).

## Step 2: Reproduce the defect

**Hypothesis (from code reading):** The `flowpulse` keyframe animates `stroke` between `var(--flow)` and `#fff`. CSS animation keyframes that set `stroke` write the animated value as the element's `stroke` *even after the animation ends* (the animation-fill or the last keyframe leaves the property at the keyframe value until something else changes it). The 10s `poll()` resets `c.style.stroke=nc` (status color), but BETWEEN polls the stroke is stuck on the activity color (`--flow`), NOT the status color. This is the "flickert / sieht anders aus" defect.

**Reproduce:**
1. Open `https://coevolution-factory-sparkling-mountain-1802.fly.dev/?lang=de`.
2. Find an ACTIVE tile (kind=discuss/develop — LED is blue/green, not grey).
3. Watch the hex border for ~10s: it should pulse white↔activity-color (flowpulse) AND stay status-colored between pulses. Observe: after the first pulse, the border stays on the activity color until the next poll overwrites it.
4. Compare to an idle tile (grey LED, no pulse) — its border stays status-colored correctly.

## Step 3: Audit findings (confirmed defects)

### F-1 (BUG): `flowpulse` permanently overrides the status stroke color
- **Where:** CSS `@keyframes flowpulse` + `.hex:not([data-kind=idle]) .hexshape{animation:flowpulse …}` (runtime.py ~3560-3561).
- **Why:** The keyframe sets `stroke:` (a presentation attribute via CSS animation). After the animation cycle, the computed `stroke` is the last keyframe value (`var(--flow)`), overriding the `data-c`-driven status stroke that `poll()` set via `c.style.stroke=nc`. Only the next `poll()` (10s) restores the status color.
- **Effect:** Active tiles' borders flicker between status-color and activity-color; visually inconsistent with idle tiles.
- **Fix direction:** Don't animate `stroke` (which fights the status color). Instead animate `stroke-width` + `box-shadow`/`filter` for the pulse, OR animate `stroke` only via a separate non-conflicting property. Recommended: replace `flowpulse` with a `box-shadow` glow pulse (doesn't touch `stroke`), keeping `stroke` = status color always.

### F-2 (MINOR): Redundant `animation` declaration
- **Where:** `.hex{animation:hexin …}` + `.hex[data-kind=…]{animation:hexin …}` (runtime.py ~3555-3559).
- **Why:** The 4 `data-kind` rules redeclare the same `hexin` animation as the base `.hex` rule — redundant; the `--flow` var is the only addition.
- **Fix direction:** Keep `animation:hexin` on `.hex` only; set `--flow` via the `data-kind` rules without re-declaring `animation`.

### F-3 (MINOR): `--flow` undefined for the base `.hex` (no data-kind)
- **Where:** `.hex:not([data-kind=idle]) .hexshape{animation:flowpulse…}` references `var(--flow,…)` but `--flow` is only defined on the 4 `data-kind` rules.
- **Why:** If a tile has `data-kind` set to something other than the 4 known kinds (e.g. a future kind), `--flow` is undefined → `stroke:var(--flow)` = invalid → stroke drops to browser default. The fallback `var(--flow,#36d6a0)` handles it, but only because of the fallback arg.
- **Fix direction:** Define a default `--flow:#36d6a0` on `.hex` so the fallback is explicit.

### F-4 (PERF, minor): `poll()` does 255 DOM reads/writes per 10s
- **Where:** `poll()` JS (~3559): `querySelectorAll('.hex')` then per tile `querySelector('.hexshape')`, `querySelector('.hexled')`, `querySelector('[data-k=sessions]')`, `querySelector('[data-k=leads]')`, plus `setAttribute`.
- **Why:** 51 tiles × ~5 queries = 255 DOM ops every 10s. Not a real bottleneck at 51, but scales poorly.
- **Fix direction (optional):** Cache element refs on the tile (`g._led = led` etc.) once, or use `requestAnimationFrame` + a single batched pass. YAGNI at 51 tiles — leave unless it janks.

### F-5 (MINOR): `poll()` sets `g.setAttribute('data-kind',…)` but CSS `flowpulse` only triggers on `:not([data-kind=idle])` — idle tiles get `data-kind=idle` which is correct, but the base `.hex` animation `hexin` runs for ALL tiles including idle. Idle tiles pulse-in once on load (intended) but never pulse again (correct). No defect — just confirm.

## Step 4: Fix plan (for the next implementation turn)

**Task 1 — Fix F-1 (the real defect):** Replace `flowpulse` `stroke` animation with a `box-shadow` glow.
- Modify CSS `@keyframes flowpulse` → animate `box-shadow` (e.g. `0 0 0px var(--ac)` → `0 0 12px var(--ac)`), and apply it to `.hexshape` (or `.hex`).
- Remove the `stroke:` animation lines so `stroke` stays = status color (`data-c`) always.
- Verify: active tiles glow (box-shadow pulse) while border stays status-colored; idle tiles don't glow.

**Task 2 — Fix F-2/F-3 (cleanup):** Consolidate `animation` + default `--flow`.
- Move `animation:hexin` to `.hex` only; `data-kind` rules set only `--flow`.
- Add `--flow:#36d6a0` default on `.hex`.

**Task 3 — Verify:**
- `node --check` the inline JS (extract `<script>(function(){…})()</script>`).
- Live: open `/?lang=de`, watch an active tile — border should stay status-colored (green for healthy) while a soft glow pulses. Idle tiles: no glow, border stays status-colored.
- Confirm no regression: hover still lightens fill, LED still shows activity color.

**Files to change:** `factory/runtime.py` (only the `.hex*` CSS block ~3555-3561 + the `flowpulse` keyframe). No JS/HTML change needed.

## Risks / tradeoffs
- `box-shadow` on an SVG `<path>` works in modern browsers but is less universally supported than `stroke` animation. Acceptable for this audience (Chromium/Firefox). Fallback: animate `stroke-width` instead (also doesn't fight the color).
- The glow pulse is subtler than the stroke-flicker — intentional (Palantir-grade calm). If a stronger signal is wanted, increase `box-shadow` radius.
