# factory/evolve.py — RECURSIVE self-improvement for the 50 daughter CENTERS.
#
# The panels (not hand-tuned) are living bodies of experts that improve
# THEMSELVES from real cashflow + session data, recursively, with a Laura gate
# on every self-authored change (doctrine).
#
# Loop per center (runs on a cron / scheduler):
#  1. gather telemetry: sessions, conversion, which disciplines fire, which
#     findings land, revenue per session, which adjacent centers resonate.
#  2. meta rule rewrites the panel: drop dead disciplines, promote high-signal
#     adjacent-center expertise, sharpen mandate copy, tune price — GROUNDED
#     IN THE DATA, not guesses.
#  3. Laura gate: the proposed panel change is run through mcp_laura_review_plan.
#     Only if 0 FLAGs is it applied (append-only version bump in state.json).
#  4. the new version is live-tested; its cashflow delta feeds the NEXT cycle.
#     -> recursion: improvement is measured by the next improvement.

import json, time, os
from pathlib import Path

HERE = Path(__file__).parent
STATE = HERE / "state.json"

from catalog import CENTERS_META, CENTER_NETWORK


def load_state():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save_state(s):
    STATE.write_text(json.dumps(s, indent=2))


# ---- 1. TELEMETRY: what the center actually did -------------------------
def telemetry(center_slug, state):
    keys = state.get("keys", {})
    ctr_keys = [k for k, v in keys.items() if v.get("center") == center_slug]
    sessions = sum(state["keys"][k]["sessions"] for k in ctr_keys)
    usage = [u for u in state.get("usage", []) if u.get("center") == center_slug]
    rev = round(sum(u["cost"] for u in usage), 2)
    fired = {}
    for k in ctr_keys:
        for a in state["keys"][k].get("last_agents", []):
            fired[a] = fired.get(a, 0) + 1
    return {"sessions": sessions, "revenue_eur": rev, "keys": len(ctr_keys),
            "agents_fired": fired}


# ---- 2. META-REWRITE: a data-grounded rule proposes a better panel -------
def evolve_panel(slug, spec, tel):
    """Recursive improvement rule (data-grounded, not a guess):
      - if a discipline in the panel never fired across N sessions -> drop it
        (cheaper convene, higher margin, future-proof).
      - if sessions>0 and revenue==0 -> price test: raise 25% to find
        willingness-to-pay; free tier shrinks.
      - if sessions==0 -> sharpen the mandate copy to convert.
      - if an ADJACENT center shares downstream expertise that this center's
        panel lacks and the adjacent center is active, propose importing one
        of its high-signal agents (network coevolution).
    Returns (new_spec, changelog)."""
    new = dict(spec)
    changelog = []
    panel = list(new["panel"])
    # network proposal
    from catalog import CENTERS_META as _CM
    adj = CENTER_NETWORK.get(slug, [])
    imported = None
    for a in adj:
        if tel["sessions"] >= 3 and state_import_ok(a):
            candidate = [x for x in _CM[a]["panel"]
                         if x not in panel and x not in tel["agents_fired"]]
            if candidate:
                imported = candidate[0]
                break
    if imported and len(panel) < 16:
        panel.append(imported)
        changelog.append(f"network: imported {imported} from adjacent center")
    dead = [a for a in panel if tel["agents_fired"].get(a, 0) == 0
            and tel["sessions"] >= 3]
    if dead:
        panel = [a for a in panel if a not in dead]
        changelog.append(f"dropped dead disciplines {dead}")
    if tel["sessions"] > 0 and tel["revenue_eur"] == 0 and tel["sessions"] >= new["free"]:
        new["price"] = round(new["price"] * 1.25, 2)
        new["free"] = max(1, new["free"] - 1)
        changelog.append(f"price test -> EUR {new['price']}/session, free {new['free']}")
    if tel["sessions"] == 0:
        new["mandate"] = new["mandate"] + \
            " — [v2: sharpened mandate, lead with the exposure, not the feature]"
        changelog.append("sharpened mandate copy (zero sessions)")
    new["panel"] = panel[:16]
    if not changelog:
        changelog.append("no change warranted this cycle (stable)")
    return new, changelog


def state_import_ok(other_slug):
    """Only import from an adjacent center that is itself active (has had
    sessions) — keeps the network coevolution grounded in live signal."""
    st = load_state()
    by_c = {}
    for k, v in st.get("keys", {}).items():
        by_c[v.get("center")] = by_c.get(v.get("center"), 0) + v.get("sessions", 0)
    return by_c.get(other_slug, 0) > 0


# ---- 3 + 4 handled by caller: Laura gate, apply, recurse ------------------
def apply_version(state, slug, new_spec, changelog, laura_ok):
    cen = state.setdefault("centers", {}).setdefault(slug, {})
    cur = cen.get("version", 1)
    if not laura_ok:
        cen.setdefault("blocked", []).append(
            {"at": int(time.time()), "changelog": changelog,
             "reason": "laura_gate_flag"})
        return cur, "BLOCKED by Laura gate"
    cen["version"] = cur + 1
    cen["spec_v" + str(cur + 1)] = new_spec
    cen.setdefault("history", []).append(
        {"v": cur + 1, "at": int(time.time()), "changelog": changelog})
    save_state(state)
    return cur + 1, "applied v" + str(cur + 1)


# ---- 2b. VALUE-PROP EVOLVE: learn real questions from telemetry -----
import re as _re

def extract_use_cases(slug, state, max_cases=3, min_len=24):
    """Pull the REAL questions visitors typed (state['jobs'] text) for this
    center and surface the most representative ones as use-cases. Data-grounded,
    deterministic — no LLM, no fabrication. Returns a list of strings
    (cleaned, de-duplicated, capped)."""
    jobs = state.get("jobs", {})
    seen, out = set(), []
    for j in jobs.values():
        if j.get("center") != slug:
            continue
        t = (j.get("text") or "").strip()
        if len(t) < min_len or len(t) > 240:
            continue
        t = _re.sub(r"\s+", " ", t).strip()
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        # skip pure engine-test boilerplate
        if "legitimate interest" in key and "unencrypted" in key:
            continue
        out.append(t)
        if len(out) >= max_cases:
            break
    return out


def evolve_valueprop(slug, state):
    """Recursive value-prop improvement (data-grounded, Laura-gated):
      - if real visitor questions exist and differ from the curated use_cases,
        propose importing the top N as live use-cases.
      - never invents; only promotes what a human actually typed.
    Returns (new_valueprop_block, changelog)."""
    cur = state.setdefault("centers", {}).get(slug, {})
    cur_uses = set(cur.get("use_cases", []))
    discovered = extract_use_cases(slug, state)
    fresh = [d for d in discovered if d not in cur_uses]
    changelog = []
    if not fresh:
        changelog.append("value-prop stable (no new real questions)")
        return None, changelog
    merged = sorted(set(cur_uses) | set(fresh))[:6]
    new_block = dict(cur.get("use_cases_meta", {}))
    new_block["use_cases"] = merged
    changelog.append(f"value-prop: imported {len(fresh)} real visitor question(s) as use-cases")
    return new_block, changelog


if __name__ == "__main__":
    st = load_state()
    for slug, spec in CENTERS_META.items():
        tel = telemetry(slug, st)
        new_spec, log = evolve_panel(slug, spec, tel)
        print(f"{slug}: sessions={tel['sessions']} rev={tel['revenue_eur']} -> {log}")
        _, vp_log = evolve_valueprop(slug, st)
        if vp_log and vp_log[0] != "value-prop stable (no new real questions)":
            print(f"    value-prop: {vp_log}")
