"""Temporal Cognition — mandatory time anchoring for all CoEvolution firms.

Simeon's doctrine (2026-07-17):
  - Every firm gets a PAST ANCHOR: its unix-epoch birth (born_at).
  - Every action gets a PRESENT ANCHOR: a live timestamp in the canonical
    format `Fri/2026-07-17T15:09:11Z/1784300951` (human + machine readable).
  - The FUTURE NORTH STAR is a fixed calendar date: 2040-09-08
    (firm anniversary party; highest earner pays). This gives the firms a
    forward-facing motivation instead of "3 years of silence".

Canonical timestamp format (machine-parseable + human-readable):
    "<weekday>/<YYYY-MM-DD>T<HH:MM:SS>Z/<unix_epoch>"
Example:
    Fri/2026-07-17T15:09:11Z/1784300951

Primary-key schema for all state records: {epoch}/{hash}
  - epoch  = unix seconds of the action (past reference point)
  - hash   = short deterministic id of the subject (e.g. sha1(slug)[:8])
  Example record id: "1784300951/a1b2c3d4"

This lets every firm collaborate on a shared timeline: plans, agreements,
and real-world anchoring — no firm ever thinks "a day passed and then 3
years of nobody talking to me".

All functions are pure + timezone-stable (UTC). No I/O.
"""
import time
import hashlib
from datetime import datetime, timezone

# Future north star: firm anniversary. Highest earner pays the party. 🎉
FUTURE_NORTH_STAR = "2040-09-08"
_NORTH_STAR_EPOCH = int(
    datetime(2040, 9, 8, 0, 0, 0, tzinfo=timezone.utc).timestamp()
)

_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def stamp(t=None):
    """Return canonical timestamp string for unix epoch t (default now).

    Format: Fri/2026-07-17T15:09:11Z/1784300951
    """
    t = int(t if t is not None else time.time())
    dt = datetime.fromtimestamp(t, tz=timezone.utc)
    wd = _WEEKDAYS[dt.weekday()]
    return f"{wd}/{dt.strftime('%Y-%m-%dT%H:%M:%SZ')}/{t}"


def parse(ts):
    """Parse a canonical timestamp back into (weekday, iso, epoch)."""
    wd, iso, epoch = ts.split("/")
    return wd, iso, int(epoch)


def epoch_of(ts):
    """Extract unix epoch from a canonical timestamp string."""
    return int(ts.split("/")[-1])


def short_hash(subject):
    """Short deterministic id for a subject (slug, name, etc.)."""
    return hashlib.sha1(subject.encode()).hexdigest()[:8]


def ts_id(t=None, subject=""):
    """Primary key for any state record: {epoch}/{hash}."""
    t = int(t if t is not None else time.time())
    return f"{t}/{short_hash(subject)}"


def born_at(existing_ts=None):
    """Past anchor for a firm. If an existing timestamp is known, derive the
    epoch from it; otherwise use now (the firm is being born right now)."""
    if existing_ts:
        return epoch_of(existing_ts) if isinstance(existing_ts, str) \
            else int(existing_ts)
    return int(time.time())


def north_star():
    """Future north star as (iso, epoch)."""
    return FUTURE_NORTH_STAR, _NORTH_STAR_EPOCH


def cognition(born_epoch, last_action_ts=None):
    """Assemble the temporal cognition block for a firm.

    past_anchor    = born epoch (string stamp)
    present_anchor = last action timestamp (or born if none yet)
    future_north_star = 2040-09-08 (fixed)
    """
    present = last_action_ts or stamp(born_epoch)
    return {
        "past_anchor": stamp(born_epoch),
        "present_anchor": present,
        "future_north_star": FUTURE_NORTH_STAR,
    }


def years_to_north_star(from_ts=None):
    """Motivation metric: years until the anniversary party."""
    if from_ts is None or from_ts == "—":
        from_ts = time.time()
    try:
        from_ts = int(from_ts)
    except (TypeError, ValueError):
        from_ts = time.time()
    return round((_NORTH_STAR_EPOCH - from_ts) / (365.25 * 86400), 2)
