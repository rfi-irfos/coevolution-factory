# "Wie sie arbeiten" (Office-Tab) — Audit + Fix-Plan

> **For Hermes:** Plan mode only. Audit the office-visualization tab inside the center modal, document what it actually does, what is wrong/weak, and propose a concrete fix. No code this turn.

**Goal:** Make the "Wie sie arbeiten" (`cp2`) tab inside the center modal correct, calm, and performant — matching the Palantir-grade "no flicker/strobe" standard — instead of the current game-like canvas that runs 60fps forever and shows fake random people.

**Architecture:** The tab is a single `<canvas id=workshop>` (1200×800) driven by `officeInit()` + `frame()` (a `requestAnimationFrame` loop) inside the modal JS (`runtime.py` ~2903-3010). It draws a top-down office floorplan: walls, decorative desks with random avatars, a meeting room, foosball, sofa, plants, and a ring of "panel desks" (the firm's agents) around a central "wartet ANFRAGE" hub. Data comes from `OFFICE_PANEL` (the firm's `panel` slugs) + `ROLE_BIOS` (real bios) + `hubActive` (set by the modal poll).

---

## Step 1: What the tab ACTUALLY does right now (read-only findings)

**Files:** `factory/runtime.py`
- Render: `center_modal_inner` builds `<div class=cmpane id=cp2>` with `<canvas class=officecanvas id=workshop width=1200 height=800>` (~2844).
- JS: `officeInit()` / `frame()` / `drawDesk()` / `drawPerson()` / `_workerAt()` (~2903-3010).
- Data injected: `__PANEL_JSON__` (panel slugs), `__ROLE_BIOS__` (slug→bio), `workshop_caption`, `desk_default` (TR string, currently `""`).

**Confirmed behaviors:**
1. **Permanent 60fps rAF loop.** `frame()` calls `requestAnimationFrame(frame)` unconditionally at the end (~2997). It runs even when the tab is hidden (modal on "Übersicht") → constant CPU. (Screenshot showed 48% CPU — this loop is the likely cause.)
2. **Random fake people.** `_panelWorkers = OFFICE_PANEL.map(...)` assigns random `skin/shirt/hair` via `_pick()` (~2950). The agents are NOT the real panel members — they're randomly colored generic blobs. No name, no role shown on the desk (the `name` argument is passed as `p`, but `drawDesk` only draws `name` if truthy — and `p` is an object, so `if(name)` is always truthy but `fillText(name,...)` prints `[object Object]`). **BUG: agent desks render `[object Object]` as the label, or nothing meaningful.**
3. **Green glow on every occupied desk.** `drawDesk` sets `ctx.shadowColor='#36d6a0'; ctx.shadowBlur=14` for any occupied desk (~2935). This is the "game glow" — loud, not calm.
4. **"wartet ANFRAGE" hub always present.** Drawn every frame at center (~2983), green when `hubActive`, grey otherwise. The text "wartet" (waiting) is shown permanently even with no pending request — reads as "stuck/dead".
5. **Slow pulse + dashed flow lines.** Hub pulses (~16s breath), dashed lines animate `lineDashOffset` (~2985). These ARE calm (no strobe) — good per the no-flicker rule.
6. **Click a desk → popup with real bio.** `workpopup` shows `ROLE_BIOS[p]` (~3010+). This part is correct and valuable.
7. **`desk_default` emptied.** Set to `""` in a prior patch (idle text removed). Bottom `deskinfo` now shows nothing.

---

## Step 2: Defects / weaknesses (ranked)

### D-1 (PERF): 60fps rAF runs forever, even hidden
- **Where:** `frame()` tail `requestAnimationFrame(function(){frame(...)});` (~2997).
- **Why:** No visibility check, no tab-active check. Burns CPU (48% in screenshot) and battery.
- **Fix:** Only run the loop when `cp2` is the visible tab; pause on tab switch / `document.hidden`. Or switch to a low-frequency `setInterval` (e.g. 2-4 fps) since motion is slow anyway.

### D-2 (BUG): Agent desks show `[object Object]` or empty label
- **Where:** `drawDesk(x,y,...,p,...)` passes the panel slug/object as `name`; `if(name){...fillText(name,...)}` (~2939). `p` is an object → `[object Object]`.
- **Why:** `name` was meant to be a string label; it's passed the raw panel entry.
- **Fix:** Pass the human label (e.g. `role_bio(p)['role']` or a short name) instead of the object. Or pull the real name from `catalog`.

### D-3 (DEFECT): Random fake avatars, not the real team
- **Where:** `_panelWorkers` random skins/shirts (~2950); `drawPerson` uses them (~2938).
- **Why:** The visualization shows generic random people, not the actual firm's agents. Undermines the "honest telemetry" standard.
- **Fix:** Either (a) label each desk with the real agent role/name + a stable color derived from the slug (deterministic, not random), or (b) drop the avatar abstraction and show role-labeled desks. At minimum: deterministic color per slug (hash) instead of `Math.random()`.

### D-4 (VISUAL): Loud green glow on every desk
- **Where:** `drawDesk` `shadowBlur=14` green (~2935).
- **Why:** Conflicts with "calm, no flicker" Palantir-grade standard. Every desk glows green constantly.
- **Fix:** Remove the constant glow; reserve a subtle accent ONLY for the hub or for the currently-hovered/clicked agent.

### D-5 (COPY): "wartet ANFRAGE" reads as stuck
- **Where:** hub text (~2983).
- **Why:** "wartet" (waiting) is always shown even with no request → looks dead.
- **Fix:** Conditional copy: show "wartet ANFRAGE" only when `hubActive`/a request is live; otherwise show a calm "bereit" / "live" state with the firm status. Or move the status into the top-right live badge only.

### D-6 (MINOR): Fixed 1200×800 canvas, CSS-scaled → blurry
- **Where:** `<canvas width=1200 height=800>` (~2846) + CSS `max-width`.
- **Why:** If container is smaller, canvas is upscaled → soft/blurry lines.
- **Fix:** Size canvas to its container via `devicePixelRatio` on init/resize.

### D-7 (MINOR): `desk_default` now empty
- **Where:** TR `desk_default=""` (~2039 area, patched earlier).
- **Why:** Bottom `deskinfo` shows nothing. Minor — the caption (`wcaption`) still shows.
- **Fix:** Restore a short honest line, or leave empty intentionally.

---

## Step 3: Proposed fix direction (pick one — confirm before implementing)

**Option A — Calm + honest (recommended):**
- D-1: pause rAF when tab hidden / use 3fps interval.
- D-2: real role labels on desks.
- D-3: deterministic per-slug color (no random people) + real names.
- D-4: remove constant glow; accent only on hover/click.
- D-5: conditional hub copy.

**Option B — Remove the canvas entirely:** Replace `cp2` with a clean static panel: agent roster (name/role/activity LED) + a small static SVG floorplan (no animation). Kills the CPU issue completely, matches "no flicker" 100%.

**Option C — Keep as-is but fix D-1/D-2 only** (minimal change, stops the CPU burn + the `[object Object]` bug, leaves the game look).

---

## Step 4: Validation (after fix)
- Open a center modal → "Wie sie arbeiten" tab.
- CPU on the tab should drop to ~0 when hidden (D-1 fixed).
- Agent desks show real role names, not `[object Object]` (D-2 fixed).
- No random-colored fake people (D-3 fixed).
- No constant green glow (D-4 fixed).
- Hub copy reflects real state (D-5 fixed).
- Click a desk → popup still shows real `ROLE_BIOS` (D-2 regression check).
- `node --check` the modal JS after changes.

**Files to change (for any option):** `factory/runtime.py` — the `officeInit`/`frame`/`drawDesk` block (~2903-3010) + the `cp2` HTML (~2844-2850) + possibly TR strings (`desk_default`, `hub_idle`).
