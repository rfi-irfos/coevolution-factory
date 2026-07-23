#!/usr/bin/env python3
"""
hermes-memory-proxy — background memory-management service for Hermes.

Runs as a systemd user service (autostart, Restart=always). Decoupled from the
Hermes conversation loop: polls reasoning blocks + session state, classifies
each extracted fact on a TERNARY VECTOR SCALE (+1 / 0 / -1), and gradually
spills durable facts into the Engram + RuVector stores — without ever blocking
the live agent.

Why this exists (Simeon, 2026-07-23):
  Hermes often hits the 75% memory watermark mid-reasoning and hiccups because
  compaction + memory-writes happen INSIDE the conversation loop. This service
  moves that work OUT of the loop: a always-on local proxy that continuously,
  gradually, and asynchronously pours important context into the persistent
  stores. No more "stuck at 75% while still reasoning".

Ternary Vector Scale (from RFI-IRFOS TIS stack):
  +1  AFFIRM   — durable, persist immediately to Engram + RuVector.
   0  TEND     — uncertain / review-later, Engram-only, low priority.
  -1  REJECT   — transient / noise, drop (do not store).

Metacog Bridge (optional, graceful-degrade):
  If lauras-agents-api is up on :8080, POST reasoning blocks to
  /pool/agents/{slug}/reflect (apply:false, read-only) and harvest gaps[].

Usage:
  python3 memory_proxy.py --once      # single tick (test mode)
  python3 memory_proxy.py --daemon    # fork to background (used by systemd)
  python3 memory_proxy.py             # foreground (default, for manual run)

Author: RFI-IRFOS (Simeon Kepp + Hermes)
License: MIT
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
import glob
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
PASTE_DIR = HERMES_HOME / "pastes"
SESSION_DIR = HERMES_HOME / "sessions"
ENGRAM_PATH = Path.home() / ".ternlang" / "engram-hash.jsonl"
RUVECTOR_PATH = Path.home() / ".ternlang" / "engram-hash.jsonl"  # same store (append-only)
STATE_PATH = HERMES_HOME / "memory_proxy_state.json"
LOG_PATH = HERMES_HOME / "memory_proxy.log"
PID_PATH = HERMES_HOME / "memory_proxy.pid"

METACOG_URL = os.environ.get("METACOG_URL", "http://localhost:8080")
METACOG_AUTH = os.environ.get("METACOG_AUTH", "local")  # NOTE: key only, not "local:*"
METACOG_SLUG = os.environ.get("METACOG_SLUG", "hermes-self")

POLL_INTERVAL = int(os.environ.get("MEMORY_PROXY_INTERVAL", "30"))  # seconds
BATCH_PER_TICK = int(os.environ.get("MEMORY_PROXY_BATCH", "5"))      # max facts/tick
MAX_PASTE_AGE_DAYS = int(os.environ.get("MEMORY_PROXY_MAX_AGE", "7"))

# Patterns that signal a durable, high-value fact in a reasoning block.
DURABLE_PATTERNS = [
    r"(HARD RULE|HARTE REGEL)",
    r"(nie|never|immer|always|NIEMALS)",
    r"(MUST NOT|darf nicht|must not|erforderlich|required)",
    r"(LAURA VOICE|für Laura|laura_log)",
    r"(Terminology|NIE 'statische Analyse'|ROOT LEVEL ANALYSIS)",
    r"(deploy|push|fly|LLB|moe-llb|Gate)",
    r"(RuVector|engram|memory)",
]
TEND_PATTERNS = [
    r"(vielleicht|maybe|perhaps|unsicher|uncertain|tend)",
    r"(\?{1,})",
]
TRANSIENT_PATTERNS = [
    r"^\s*[-*]\s*\w+:\s*$",  # empty bullet
    r"^(DEBUG|TRACE|VERBOSE):",
    r"\b(tmp|temp|/tmp/)\b",
]

_running = True


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Ternary classification
# ---------------------------------------------------------------------------
def classify_trit(text: str) -> int:
    """Return +1 (affirm), 0 (tend), or -1 (reject) for a candidate fact."""
    t = text.strip()
    if not t or len(t) < 4:
        return -1
    for pat in TRANSIENT_PATTERNS:
        if re.search(pat, t, re.IGNORECASE):
            return -1
    for pat in DURABLE_PATTERNS:
        if re.search(pat, t, re.IGNORECASE):
            return 1
    for pat in TEND_PATTERNS:
        if re.search(pat, t, re.IGNORECASE):
            return 0
    # default: medium-value → tend (Engram-only, low priority)
    return 0


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------
def extract_facts_from_paste(path: Path) -> list[str]:
    """Pull candidate facts (one per non-empty line / sentence) from a paste."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    # Split into sentences/lines, drop very short or pure-symbol lines.
    parts = re.split(r"(?:\n|\.\s|\?\s|!\s)", text)
    facts = []
    for p in parts:
        p = p.strip()
        if 8 <= len(p) <= 400:
            facts.append(p)
    return facts


# ---------------------------------------------------------------------------
# Persistent store (Engram + RuVector share the append-only JSONL)
# ---------------------------------------------------------------------------
def append_engram(op: str, fact_type: str, scope: str, content: str, trit: int) -> bool:
    rec = {
        "op": op,
        "id": int(time.time() * 1000),
        "t_ms": int(time.time() * 1000),
        "type": fact_type,
        "scope": scope,
        "trit": trit,  # ternary vector scale: +1 / 0 / -1
        "content": content,
    }
    try:
        with open(ENGRAM_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return True
    except Exception as e:
        log(f"ENGram write failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Metacog bridge (optional, read-only, graceful-degrade)
# ---------------------------------------------------------------------------
def metacog_reflect(text: str) -> dict | None:
    """POST a reasoning block to the Rust Metacog agent (read-only reflect).
    Returns gaps[] if reachable, else None (caller ignores)."""
    url = f"{METACOG_URL}/pool/agents/{METACOG_SLUG}/reflect"
    body = json.dumps({
        "text": text[:4000],
        "last_input": "hermes memory proxy spill",
        "last_response": text[:4000],
        "apply": False,  # read-only — never auto-apply
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={
            "Authorization": f"Bearer {METACOG_AUTH}",
            "Content-Type": "application/json",
        }, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, OSError):
        return None  # graceful degrade: server not up, skip


# ---------------------------------------------------------------------------
# State (cursor so we never re-process the same paste)
# ---------------------------------------------------------------------------
def load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"seen_pastes": {}, "tick": 0}


def save_state(state: dict) -> None:
    try:
        STATE_PATH.write_text(json.dumps(state), encoding="utf-8")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# One tick
# ---------------------------------------------------------------------------
def tick(state: dict) -> int:
    """Process one gradual batch. Returns number of facts spilled."""
    state["tick"] = state.get("tick", 0) + 1
    spilled = 0
    seen = state.setdefault("seen_pastes", {})
    now = time.time()
    max_age = MAX_PASTE_AGE_DAYS * 86400

    if PASTE_DIR.exists():
        for paste in sorted(PASTE_DIR.glob("*.txt"), key=os.path.getmtime, reverse=True):
            if spilled >= BATCH_PER_TICK:
                break
            pkey = str(paste)
            try:
                mtime = paste.stat().st_mtime
            except Exception:
                continue
            if now - mtime > max_age:
                seen[pkey] = "expired"
                continue
            if seen.get(pkey) in ("done", "expired"):
                continue
            facts = extract_facts_from_paste(paste)
            for fact in facts:
                if spilled >= BATCH_PER_TICK:
                    break
                trit = classify_trit(fact)
                if trit == -1:
                    continue  # reject → drop, do not store
                # +1 → Engram + RuVector (persist); 0 → Engram-only (tend)
                scope = "engram+rvector" if trit == 1 else "engram"
                if append_engram("Remember", "memory_proxy_spill", scope, fact, trit):
                    spilled += 1
                    # Occasionally ask Metacog for a review (throttled).
                    if trit == 1 and spilled == 1 and state["tick"] % 10 == 0:
                        res = metacog_reflect(fact)
                        if res and isinstance(res, dict):
                            gaps = res.get("gaps", [])
                            for g in gaps[:2]:
                                append_engram(
                                    "MetacogGap", "metacog_review", "engram",
                                    f"{g.get('area','?')}: {g.get('why','?')} "
                                    f"[{g.get('severity','?')}]", 0,
                                )
            seen[pkey] = "done"
    save_state(state)
    return spilled


# ---------------------------------------------------------------------------
# Daemon
# ---------------------------------------------------------------------------
def handle_signal(signum, frame):
    global _running
    log(f"Received signal {signum}, shutting down.")
    _running = False


def run_daemon():
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    PID_PATH.write_text(str(os.getpid()), encoding="utf-8")
    log("memory_proxy started (daemon).")
    state = load_state()
    while _running:
        try:
            n = tick(state)
            if n:
                log(f"tick {state['tick']}: spilled {n} fact(s)")
        except Exception as e:
            log(f"tick error: {e}")
        # Sleep in small slices so SIGTERM is responsive.
        for _ in range(POLL_INTERVAL):
            if not _running:
                break
            time.sleep(1)
    PID_PATH.unlink(missing_ok=True)
    log("memory_proxy stopped.")


def run_once():
    state = load_state()
    n = tick(state)
    log(f"--once: spilled {n} fact(s) (tick {state['tick']})")


def main():
    ap = argparse.ArgumentParser(description="Hermes memory proxy service")
    ap.add_argument("--daemon", action="store_true", help="fork to background")
    ap.add_argument("--once", action="store_true", help="single tick, then exit")
    args = ap.parse_args()

    if args.once:
        run_once()
        return
    if args.daemon:
        # Double-fork to detach (systemd does this itself, but be safe).
        if os.fork() == 0:
            os.setsid()
            if os.fork() == 0:
                run_daemon()
            os._exit(0)
        os._exit(0)
    else:
        run_daemon()


if __name__ == "__main__":
    main()
