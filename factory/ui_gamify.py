"""Gamification + Hive-Mind UI helpers (Simeon: the whole site must be
gamified, honeycomb, not SV squares). Pure functions, no side effects —
used by firms_grid / index / center_page renderers.

WWND/BBTR: a hive is not a grid of boxes. It is a honeycomb of living cells,
each with a level, a trail strength, and a march toward the 2040 Jubilaeum.
Gamification here means legibility + life, not dark patterns.
"""
import math
from datetime import datetime, timezone


# Honeycomb hex clip-path (CSS). Reused by every tile so the whole site is
# one organic hive, not a spreadsheet of squares.
HONEYCOMB_CLIP = (
    "polygon(50% 0%, 93% 25%, 93% 75%, 50% 100%, 7% 75%, 7% 25%)"
)


def firm_level(slug, problems_solved=0, vp_strength=0.0):
    """A firm's level: 1 + floor(log of its real impact).

    Not a vanity number — it reflects actual solved problems + trail.
    """
    score = problems_solved + vp_strength * 5.0
    if score <= 0:
        return 1
    return 1 + int(math.log2(score + 1))


def jubilee_progress(born_epoch):
    """Progress (0..1) from firm birth toward the 2040 Jubilaeum party.

    The whole hive marches toward one north-star date; this bar shows how
    far each cell has come. Honest: based on real elapsed time.
    """
    north = datetime(2040, 9, 8, tzinfo=timezone.utc).timestamp()
    now = datetime.now(timezone.utc).timestamp()
    if born_epoch is None:
        born_epoch = now
    if north <= born_epoch:
        return 1.0
    elapsed = now - born_epoch
    if elapsed < 0:
        return 0.0
    total = north - born_epoch
    return round(max(0.0, min(1.0, elapsed / total)), 4)


def achievements(slug, problems_solved=0, vp_strength=0.0, revenue_eur=0.0,
                  crisis_survived=False):
    """Earned badges for a firm. Each is a real, verifiable milestone."""
    badges = []
    if problems_solved >= 1:
        badges.append(("first_solve", "Erstes Problem gelöst"))
    if vp_strength >= 1.0:
        badges.append(("trail", "Pheromon-Trail etabliert"))
    if revenue_eur >= 25.0:
        badges.append(("first_partner", "Erster Partner (€25+)"))
    if crisis_survived:
        badges.append(("crisis_survivor", "Krise als 0-status überstanden"))
    return badges


def hex_css():
    """Honeycomb clip-path CSS snippet for tiles. One hive, no squares."""
    return HONEYCOMB_CLIP
