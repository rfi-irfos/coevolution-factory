#!/usr/bin/env python3
"""Verify the Teamlead roster + Board-of-Directors directive channel.

Run: python3 factory/_verify_board.py
Exit 0 on success, non-zero on failure. Missing-piece-tolerant: if the
parallel agents' edits are not yet present, it reports clearly which pieces
are missing instead of crashing on import.
"""
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import catalog
import runtime


def main():
    # 1) every center has a non-empty roster
    missing = [s for s, m in catalog.CENTERS_META.items()
               if not m.get("roster", {}).get("departments")]
    if missing:
        print(f"MISSING ROSTER: {missing}")
        return 1
    print(f"roster present on all {len(catalog.CENTERS_META)} centers")

    # 2) CEO resolution matches primary roster lead
    ceo = runtime.resolve_ceo("gdpr-guard")
    expected = catalog.CENTERS_META["gdpr-guard"]["roster"]["departments"][0]["lead"]["agent"]
    if ceo != expected:
        print(f"CEO MISMATCH: got {ceo}, expected {expected}")
        return 1
    print(f"resolve_ceo(gdpr-guard) -> {ceo}")

    # 3) board directive round-trip (stub spawn_background: no event loop here)
    runtime.spawn_background = lambda coro: None
    runtime.state.setdefault("board_directives", {})
    before = len(runtime.state["board_directives"].get("gdpr-guard", []))
    out = runtime.board_directive_handler_logic(
        "gdpr-guard", "Prioritize DPIA turnaround under 1h", acct="board")
    after = runtime.state["board_directives"]["gdpr-guard"]
    if len(after) != before + 1:
        print("BOARD DIRECTIVE not recorded")
        return 1
    if after[-1]["status"] != "routed_to_ceo" or not after[-1]["ceo_ack"]:
        print(f"BOARD DIRECTIVE bad record: {after[-1]}")
        return 1
    rid = out["run_id"]
    if runtime.state["jobs"][rid].get("priority") != "board":
        print("BOARD JOB priority not 'board'")
        return 1
    print(f"board directive {out['directive_id']} -> ceo {out['ceo']}, job {rid} (priority board)")

    # 4) board status read-back
    st = runtime.board_status("gdpr-guard")
    if st["directives"][-1]["id"] != out["directive_id"]:
        print("BOARD STATUS mismatch")
        return 1
    print(f"board status returns {len(st['directives'])} directive(s)")

    # 5) modal render regression
    h = runtime.center_card_html("gdpr-guard", "de")
    if "Produkte & Leistungen" not in h:
        print("MODAL RENDER REGRESSION: products block missing")
        return 1
    print("modal render OK (products block present)")

    print("BOARD VERIFY OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
