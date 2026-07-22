#!/usr/bin/env python3
"""Verify the ant-farm (agent grid + antfarm page) contract.

This is a DEPLOY-PREP verification script. It checks:
  1. agent-grid SHAPE  — build_agent_grid()['firms'] keys match CENTERS_META.
  2. ACTIVITY KIND     — a seeded 'develop' job for 'gdpr-guard' shows up in
                         that firm's agent kinds (Agent A: activity_kind on jobs).
  3. ANTFARM HTML      — build_antfarm_html('de') contains the German heading,
                         the gdpr-guard center, a cmd console block, and the
                         board-directive endpoint (Agent B: /antfarm + /api/agent-grid).
  4. MODAL REGRESSION  — center_card_html('gdpr-guard','de') still renders the
                          'Produkte & Leistungen' block.

Run:  python3 factory/_verify_antfarm.py
Exit 0 on full success, non-zero on failure.

MISSING-PIECE-TOLERANT: if the parallel agents (Agent A activity_kind,
Agent B grid/antfarm) have not merged yet, the script reports *which*
pieces are missing instead of crashing on import. It never mutates
state.json (in-memory only).
"""

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import catalog  # noqa: E402
import runtime  # noqa: E402


def _collect_strings(obj):
    """Recursively yield all string values found in a data structure."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _collect_strings(v)
    elif isinstance(obj, (list, tuple, set)):
        for v in obj:
            yield from _collect_strings(v)


def _develop_present(firm):
    """Return True if 'develop' appears among a firm's agent/activity kinds.

    Defensive: the exact grid shape is owned by Agent B, so we look for the
    token both in common candidate keys and anywhere in the firm payload.
    """
    # Explicit candidate keys where kinds/activity might live.
    for key in ("kinds", "agent_kinds", "activity_kinds", "activities"):
        val = firm.get(key)
        if val is None:
            continue
        flat = {str(x) for x in _collect_strings(val)}
        if "develop" in flat:
            return True
    # Fallback: anywhere in the firm payload.
    if "develop" in {str(x) for x in _collect_strings(firm)}:
        return True
    return False


def main():
    checks = []  # (name, ok, detail)
    missing_pieces = []  # human-readable list of absent contract pieces

    # ------------------------------------------------------------------
    # 0) sanity: runtime + catalog importable (must not crash).
    # ------------------------------------------------------------------
    checks.append(("import runtime/catalog", True,
                   f"{len(catalog.CENTERS_META)} centers in CENTERS_META"))

    # ------------------------------------------------------------------
    # 1) agent-grid SHAPE
    # ------------------------------------------------------------------
    if not hasattr(runtime, "build_agent_grid"):
        missing_pieces.append("runtime.build_agent_grid (Agent B: /api/agent-grid)")
        checks.append(("agent-grid shape", False,
                       "build_agent_grid not present — Agent B not merged"))
    else:
        try:
            grid = runtime.build_agent_grid()
        except TypeError as e:
            checks.append(("agent-grid shape", False,
                           f"build_agent_grid() signature mismatch: {e}"))
            missing_pieces.append("runtime.build_agent_grid call shape")
            grid = None

        if grid is not None:
            if "firms" not in grid:
                checks.append(("agent-grid shape", False,
                               "build_agent_grid() lacks 'firms' key"))
                missing_pieces.append("grid 'firms' key (Agent B)")
            else:
                got = set(grid["firms"].keys())
                exp = set(catalog.CENTERS_META.keys())
                if got == exp:
                    checks.append(("agent-grid shape", True,
                                   f"{len(got)} firms == {len(exp)} centers"))
                else:
                    missing = exp - got
                    extra = got - exp
                    msg = "firm keys mismatch"
                    if missing:
                        msg += f" | missing firms: {sorted(missing)}"
                    if extra:
                        msg += f" | unexpected firms: {sorted(extra)}"
                    checks.append(("agent-grid shape", False, msg))
                    missing_pieces.append("agent-grid firm coverage (Agent B)")

    # ------------------------------------------------------------------
    # 2) ACTIVITY KIND — seed a 'develop' job for gdpr-guard, then check
    #    it surfaces in that firm's agent kinds.
    # ------------------------------------------------------------------
    if "agent-grid shape" in {c[0] for c in checks} and \
            not any(c[0] == "agent-grid shape" and c[1] for c in checks):
        # grid unavailable -> cannot verify activity_kind either way.
        checks.append(("activity kind (develop)", False,
                       "skipped: build_agent_grid unavailable"))
        missing_pieces.append("activity_kind in grid (Agent A/B)")
    elif hasattr(runtime, "build_agent_grid"):
        # Seed an in-memory job (Agent A's shape: activity_kind on jobs).
        rid = "_verify_antfarm_develop_seed"
        runtime.state.setdefault("jobs", {})[rid] = {
            "center": "gdpr-guard",
            "activity_kind": "develop",
            "status": "running",
            "created": int(time.time()),
            "text": "verify seed: develop job",
            "panel": [],
        }
        grid = runtime.build_agent_grid()
        firm = (grid.get("firms") or {}).get("gdpr-guard")
        if firm is None:
            checks.append(("activity kind (develop)", False,
                           "gdpr-guard firm missing from grid"))
            missing_pieces.append("gdpr-guard firm (Agent B)")
        elif _develop_present(firm):
            checks.append(("activity kind (develop)", True,
                           "'develop' present in gdpr-guard firm kinds"))
        else:
            checks.append(("activity kind (develop)", False,
                           "'develop' NOT found in gdpr-guard firm kinds "
                           f"-> {firm!r}"))
            missing_pieces.append("activity_kind on jobs -> grid (Agent A)")

    # ------------------------------------------------------------------
    # 3) ANTFARM HTML (Agent B: /antfarm page + cmd console + board endpoint)
    # ------------------------------------------------------------------
    if not hasattr(runtime, "build_antfarm_html"):
        missing_pieces.append("runtime.build_antfarm_html (Agent B: /antfarm)")
        checks.append(("antfarm HTML", False,
                       "build_antfarm_html not present — Agent B not merged"))
    else:
        html = runtime.build_antfarm_html("de")
        expectations = {
            "Ameisenhaufen": "German ant-farm heading",
            "gdpr-guard": "gdpr-guard center rendered",
            'class="cmd"': "cmd console block",
            "/api/board/directive": "board-directive endpoint wired",
        }
        ok = True
        for token, label in expectations.items():
            present = token in html
            if not present:
                ok = False
                missing_pieces.append(f"antfarm HTML token {token!r} ({label})")
        if ok:
            checks.append(("antfarm HTML", True,
                           "Ameisenhaufen + gdpr-guard + cmd console + board endpoint"))
        else:
            failed = [t for t in expectations if t not in html]
            checks.append(("antfarm HTML", False,
                           f"missing tokens: {failed}"))

    # ------------------------------------------------------------------
    # 4) MODAL RENDER REGRESSION (center_card_html must still render products)
    # ------------------------------------------------------------------
    if not hasattr(runtime, "center_card_html"):
        missing_pieces.append("runtime.center_card_html (unexpected; modal core)")
        checks.append(("modal render regression", False,
                       "center_card_html not present"))
    else:
        h = runtime.center_card_html("gdpr-guard", "de")
        if "Produkte & Leistungen" in h:
            checks.append(("modal render regression", True,
                           "products block present (Produkte & Leistungen)"))
        else:
            checks.append(("modal render regression", False,
                           "Produkte & Leistungen block MISSING — regression!"))
            missing_pieces.append("modal products block (regression)")

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------
    print("=" * 64)
    print("ANT-FARM VERIFY")
    print("=" * 64)
    for name, ok, detail in checks:
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}: {detail}")
    print("-" * 64)

    # NOTE: must index c[1] (the ok flag) explicitly here. A generator like
    # `any(not ok for c in checks)` would close over the loop variable `ok`
    # left bound from the report loop above (always True on the last row),
    # which would silently mask every failure.
    hard_fail = any(not c[1] for c in checks if c[0] in (
        "agent-grid shape", "activity kind (develop)", "antfarm HTML",
        "modal render regression"))
    # Missing-piece tolerance: if Agent A/B functions are absent the contract
    # is still unmet, but we report *which* pieces are missing instead of
    # crashing on import. Either way we exit non-zero when anything failed.
    any_real_fail = any(not c[1] for c in checks)

    if missing_pieces:
        print("MISSING PIECES (parallel agents not yet merged):")
        for m in sorted(set(missing_pieces)):
            print(f"   - {m}")

    if any_real_fail:
        print("ANT-FARM VERIFY: INCOMPLETE / FAIL")
        return 1

    print("ANT-FARM VERIFY OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
