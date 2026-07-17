"""Governance defaults — Simeon's hard-coded decisions for ALL firms.

These are NOT suggestions. They are the operating constitution for every
CoEvolution firm (standing center, daughter, spawned candidate). Set once,
applied to all. Changed only by an explicit "simeon approves" decision.

Doctrine (Q&A session 2026-07-17, simeon approves):
  * FIRMS ARE AGENTS. Every firm pings every 12h (heartbeat). No "7 days of
    silence" panic trigger — regular pulse, then decide.
  * ACTION THRESHOLD: on each 12h ping, the firm checks its state. If it
    recognises "ok we must act now" (no traffic, no value delivered, no
    ecocentric traction), it MUST act.
  * MIN LEGAL PATHS = 3. Never A/B. Always A/B/C. (Core RFI-IRFOS doctrine:
    if a thing doesn't work, there are always >=3 legal alternatives.)
  * EXPERIMENT WINDOW = 7 days. The 3 paths are run as A/B/C strategy tests
    for one week with data collection. Never only A/B.
  * ORIENTATION = ecocentric. Firms must make themselves useful in the real
    physical world (Wall-E mode), not "human-centered optimized". A hypothesis
    is valid only if it is good for everything, not just us.
  * DEFAULT STATE = tend. Firms start in uncertainty/hold, not affirm. They
    raise hypotheses and validate slowly (Wall-E collecting), never rush.
  * LUNAR PLAN TRACKING: deterministic moon-phase cycle drives plan rhythm:
      new moon        -> set new plans
      first quarter   -> launch
      full moon       -> peak / validation
      last quarter    -> review / wind down
    Computed locally (no API, no network) — 29.53-day synodic period.

All values here are the single source of truth. runtime/virtual_firm/daily_spawn
import DEFAULTS and never re-decide these locally.
"""
from datetime import datetime, timezone

# Heartbeat: every firm pings itself this often (hours).
PING_INTERVAL_HOURS = 12

# Action threshold: a firm MUST act when its 12h ping shows no traction.
# "no traction" = zero sessions AND zero revenue in the trailing window.
ACTION_TRAILING_HOURS = 12  # evaluate the last ping window

# Minimum number of distinct legal paths a firm must propose before acting.
MIN_LEGAL_PATHS = 3

# A/B/C experiment duration (days). Never shorter, never only A/B.
EXPERIMENT_WINDOW_DAYS = 7

# Worldview for hypothesis validation.
ORIENTATION = "ecocentric"  # not "human-centered"

# Firms begin in hold/uncertainty, not affirm.
DEFAULT_STATE = "tend"

# Lunar cycle (deterministic, no API).
LUNAR_PERIOD_DAYS = 29.53059
# Reference new moon (UTC). Known astronomical value; anchor for all phases.
_REFERENCE_NEW_MOON = datetime(2026, 7, 14, 10, 43, 0, tzinfo=timezone.utc)


def lunar_phase_name(dt=None):
    """Return (phase_name, days_since_new_moon, illumination_0_1) for dt.

    phase_name ∈ {new, first_quarter, full, last_quarter, waxing, waning}.
    Deterministic — no network. Used by firms to track plan rhythm.
    """
    dt = dt or datetime.now(timezone.utc)
    delta_days = (dt - _REFERENCE_NEW_MOON).total_seconds() / 86400.0
    phase = (delta_days % LUNAR_PERIOD_DAYS) / LUNAR_PERIOD_DAYS  # 0..1
    # illumination proxy: 0 at new moon, 1 at full moon
    import math
    illum = round((1 - math.cos(2 * math.pi * phase)) / 2, 3)
    if phase < 0.0625 or phase >= 0.9375:
        name = "new"
    elif phase < 0.1875:
        name = "waxing"
    elif phase < 0.3125:
        name = "first_quarter"
    elif phase < 0.4375:
        name = "waxing"
    elif phase < 0.5625:
        name = "full"
    elif phase < 0.6875:
        name = "waning"
    elif phase < 0.8125:
        name = "last_quarter"
    else:
        name = "waning"
    return name, round(delta_days % LUNAR_PERIOD_DAYS, 2), illum


def plan_phase(dt=None):
    """Map the current lunar phase to the firm's plan action."""
    name, _, _ = lunar_phase_name(dt)
    return {
        "new": "set_new_plans",
        "first_quarter": "launch",
        "full": "peak_validation",
        "last_quarter": "review_wind_down",
        "waxing": "build",
        "waning": "consolidate",
    }.get(name, "build")


# Single source of truth for all firms.
DEFAULTS = {
    "ping_interval_hours": PING_INTERVAL_HOURS,
    "action_trailing_hours": ACTION_TRAILING_HOURS,
    "min_legal_paths": MIN_LEGAL_PATHS,
    "experiment_window_days": EXPERIMENT_WINDOW_DAYS,
    "orientation": ORIENTATION,
    "default_state": DEFAULT_STATE,
    "lunar_period_days": LUNAR_PERIOD_DAYS,
}
