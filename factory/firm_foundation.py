#!/usr/bin/env python3
"""Firm Foundation & Autonomous Learning (backend-only, no UI).

Every standing center ("Wabe") gets a persistent learning record inside
``state['firm_foundation'][slug]``. The record is the firm's *memory*: what
it tried, what failed, what Laura blocked, and what it learned. A daily
reflection pass turns those lessons into a stronger foundation — identifying
capability gaps and raising a ``reflection_score`` as the firm demonstrably
learns from its own mistakes.

This module NEVER touches the UI. It only reads/writes ``state`` and logs.
Designed so the firms improve autonomously (Laura's wish: they solve their
own problems) without any human in the loop.

State shape (one per center slug):
    state['firm_foundation'][slug] = {
        "created": int,
        "last_reflection": int,
        "reflection_score": float,   # 0.0..1.0 foundation strength
        "lessons": [                  # append-only, capped
            {"ts": int, "kind": "failure"|"success"|"correction"|"gap",
             "context": str, "lesson": str, "meta": dict|None,
             "applied": bool},        # True once the firm acted on it
        ],
        "capabilities": {             # what the firm can draw on
            "agents": [slug, ...],    # engine agents it has convened
            "skills": [str, ...],     # inferred competencies
            "gaps": [str, ...],       # things it lacks (from lessons)
        },
        "corrections_applied": int,   # how many blocks it learned from
        "launches": int,              # how many offerings it shipped
    }
"""
import time

import os
import json
import urllib.request
from pathlib import Path

# Where generated sample products live (one JSON per firm, real output from
# the live engine — never a placeholder).
_HERE = Path(__file__).parent
STATE_DIR = os.environ.get("FT_STATE_DIR", str(_HERE))
PRODUCT_DIR = Path(STATE_DIR) / "products"
_PRODUCT_TTL = 7 * 24 * 3600  # refresh at most once a week

# Engine access (mirrors factory_spawn_agent.py _call_engine_local, sync form).
_ENGINE_URL = os.environ.get("FT_ENGINE_URL", "https://lauras-agents-api.fly.dev")
_ENGINE_KEY = os.environ.get("FT_ENGINE_KEY", "")


def _engine_call(text, agents, timeout=120):
    """Synchronous call to the live engine's /pool/team. Returns the text
    answer or a fallback string on any failure (so we never crash the cron).
    Retries once on transport errors."""
    last = ""
    for _attempt in range(2):
        try:
            hdrs = {"Authorization": f"Bearer {_ENGINE_KEY}",
                    "Content-Type": "application/json"}
            body = json.dumps({"text": text, "agents": agents}).encode()
            req = urllib.request.Request(
                _ENGINE_URL.rstrip("/") + "/pool/team",
                data=body, headers=hdrs, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode())
            ans = data.get("answer") or data.get("result") or data.get("text") or ""
            if not ans and isinstance(data, dict):
                resp = data.get("responses")
                if isinstance(resp, list) and resp:
                    # Only pull REAL content out of each response element — if a
                    # response is a dict with no content/text (e.g. it carries a
                    # raw system_prompt / debug envelope), skip it rather than
                    # serialising that internal junk into the answer. This is the
                    # fix for the bug where "Beispiel-Ergebnis" cards rendered the
                    # agent's system_prompt verbatim instead of a deliverable.
                    parts = []
                    for x in resp:
                        c = x.get("content") if isinstance(x, dict) else None
                        if not c:
                            c = x.get("text") if isinstance(x, dict) else None
                        if not c and isinstance(x, str):
                            c = x
                        if c and str(c).strip():
                            parts.append(str(c))
                    ans = "\n".join(parts)
            if not ans:
                # No usable answer text — do NOT fall back to json.dumps(data),
                # which would dump the raw response envelope (system_prompt etc.)
                # into a user-facing card. Return empty so callers skip rendering.
                return ""
            if isinstance(ans, list):
                ans = "\n".join(str(a) for a in ans)
            return str(ans).strip()
        except Exception as e:  # noqa: BLE001 — never block the cron
            last = f"{type(e).__name__}: {e}"
            continue
    return ""


def generate_sample_product(slug, force=False):
    """Proactively build a REAL example deliverable for a firm via the live
    engine, and persist it as JSON. Returns the product dict (or None on
    failure / no catalog entry). Never returns a placeholder.
    """
    try:
        from runtime import CENTERS
    except Exception:
        try:
            import runtime  # noqa
            CENTERS = runtime.CENTERS
        except Exception:
            return None
    center = CENTERS.get(slug)
    if not center:
        return None
    PRODUCT_DIR.mkdir(parents=True, exist_ok=True)
    path = PRODUCT_DIR / f"{slug}.json"
    if not force and path.exists():
        try:
            rec = json.load(open(path))
            if time.time() - rec.get("generated_at", 0) < _PRODUCT_TTL:
                return rec  # fresh enough
        except Exception:
            pass
    panel = center.get("panel") or []
    vp = center.get("value_prop", "")
    name = center.get("name", slug)
    prompt = (
        f"You are the standing expert team for '{name}'. Produce a concrete, "
        f"real example deliverable a prospective client would receive. "
        f"Domain: {vp}. Write a short but genuinely useful sample output "
        f"(3-6 bullet points or a compact checklist) that demonstrates the "
        f"team's actual value — no marketing fluff, no 'contact us'. "
        f"This is a real artifact, not a placeholder."
    )
    answer = _engine_call(prompt, panel)
    if not answer:
        if path.exists():
            try:
                return json.load(open(path))
            except Exception:
                return None
        return None
    product = {
        "slug": slug,
        "title": f"Beispiel-Ergebnis: {name}",
        "summary": answer[:1200],
        "body": answer,
        "generated_at": int(time.time()),
        "agents": panel,
        "sample": True,
    }
    try:
        json.dump(product, open(path, "w"), ensure_ascii=False, indent=2)
    except Exception:
        pass
    return product


def load_sample_product(slug):
    """Load a previously generated product (or None).

    Guards against serving a corrupt/debug artifact: if the stored body
    contains a raw agent envelope (system_prompt / 'agent': / raw_response)
    instead of a real deliverable, treat it as missing so the card is
    skipped rather than dumping internal junk to the visitor.
    """
    path = PRODUCT_DIR / f"{slug}.json"
    if path.exists():
        try:
            rec = json.load(open(path))
            body = str(rec.get("body") or rec.get("summary") or "")
            _JUNK = ("system_prompt", "'agent':", '"agent":', "raw_response",
                     "complete':", "complete\":")
            if any(tok in body for tok in _JUNK):
                # Corrupt artifact — do not render it.
                return None
            return rec
        except Exception:
            return None
    return None

# Hard caps so state never grows unbounded.
_MAX_LESSONS = 200
_FOUNDATION_KEY = "firm_foundation"

# A brand-new firm starts at a deliberately modest score — it has to EARN
# strength by learning, not be handed it.
_INITIAL_SCORE = 0.35


def ensure_foundation(state, slug):
    """Idempotent: create the foundation record for a center if missing."""
    ff = state.setdefault(_FOUNDATION_KEY, {})
    if slug not in ff:
        ff[slug] = {
            "created": int(time.time()),
            "last_reflection": 0,
            "reflection_score": _INITIAL_SCORE,
            "lessons": [],
            "capabilities": {"agents": [], "skills": [], "gaps": []},
            "corrections_applied": 0,
            "launches": 0,
        }
    return ff[slug]


def record_lesson(state, slug, kind, context, lesson, meta=None, gap=None):
    """Append a lesson to a firm's memory.

    kind: 'failure' | 'success' | 'correction' | 'gap'
    gap: optional str describing a missing capability (added to capabilities.gaps)
    Returns the lesson dict (or None if the firm record was missing).
    """
    rec = ensure_foundation(state, slug)
    lesson_rec = {
        "ts": int(time.time()),
        "kind": kind,
        "context": context[:400],
        "lesson": lesson[:400],
        "meta": meta,
        "applied": False,
        "origin": slug,
    }
    rec["lessons"].append(lesson_rec)
    # bound the list
    if len(rec["lessons"]) > _MAX_LESSONS:
        rec["lessons"] = rec["lessons"][-_MAX_LESSONS:]
    if gap:
        gaps = rec["capabilities"].setdefault("gaps", [])
        if gap not in gaps:
            gaps.append(gap)
    # ── cross-firm learning: publish transferable lessons to the shared pool
    if kind in ("correction", "success"):
        try:
            publish_to_global(state, lesson_rec)
        except Exception as _e:
            print(f"[learning] publish_global failed: {_e}", flush=True)
    return lesson_rec


# ---------------------------------------------------------------------------
# RFI-IRFOS CORE DIRECTIVE — the 90/10 principle. This is the bedrock every
# firm is built on. It is GLOBAL, immutable (only seeded once, never mutated
# by a firm), and every firm references it. No 100% certainty exists; we assume
# 90% absolute confidence AND bake in 10% that EVERYTHING fails. Because the
# uncertainty is priced in from the start, the system becomes "100%-safer"
# (not perfect) — calculable risk instead of a blind flight.
# ---------------------------------------------------------------------------
_CORE_DIRECTIVE = {
    "id": "rfi-irfos-core-90-10",
    "name": "90/10 Principle",
    "text": (
        "There is NO 100% certain system. We assume 90% absolute confidence "
        "AND price in 10% that EVERYTHING fails — from the very start. Because "
        "the uncertainty is baked in upfront, the result is a 100%-safer "
        "(not perfect) system: calculable risk, never a blind flight. Any claim "
        "of '100%', 'guaranteed', 'zero risk' is a violation of this directive."
    ),
    "rules": [
        "no_absolute_claims: '100%'/'guaranteed'/'zero risk' are forbidden",
        "always_price_risk: state the 10% failure mode explicitly",
        "calculable_over_perfect: name the risk, don't hide it",
    ],
}


def ensure_core_directive(state):
    """Seed the immutable core directive ONCE. Never overwritten by a firm."""
    ff = state.setdefault(_FOUNDATION_KEY, {})
    if _CORE_KEY not in ff:
        ff[_CORE_KEY] = dict(_CORE_DIRECTIVE)
    return ff[_CORE_KEY]


# Inject the 90/10 as the FIRST cross-firm lesson so every firm absorbs it
# on its very first reflect (before any mistake is even made).
def seed_core_lesson(state):
    ff = state.setdefault(_FOUNDATION_KEY, {})
    g = ff.setdefault(_GLOBAL_KEY, {
        "lessons": [],
        "published_by": {},
        "absorbed_by": {},
    })
    core_lesson = {
        "ts": int(time.time()),
        "kind": "correction",
        "lesson": ("No '100%'/'guaranteed'/'zero risk' claims (RFI-IRFOS 90/10 "
                   "directive): assume 90% confidence + 10% total failure, "
                   "priced in upfront = calculable risk, not a blind flight."),
        "from": "core-directive",
    }
    for e in g["lessons"]:
        if e.get("from") == "core-directive":
            return  # already seeded
    g["lessons"].insert(0, core_lesson)


_CORE_KEY = "_core_directive"
_GLOBAL_KEY = "_global"
_MAX_GLOBAL = 300


def _generalise(lesson_rec):
    """Strip firm-specific specifics so a lesson transfers across firms.

    We keep the *shape* of the lesson (what kind of mistake/success) but drop
    the exact slug/context so another firm can apply it to its own domain.
    e.g. 'GDPR mandate blocked: absolute language' -> 'avoid absolute/guarantee
    language in mandates (Laura blocks it)'."""
    kind = lesson_rec.get("kind")
    raw = lesson_rec.get("lesson", "")
    # heuristic generalisation: pull out transferable phrases
    lowered = raw.lower()
    if "absolute" in lowered or "guarantee" in lowered or "100%" in raw:
        return ("correction",
                "Avoid absolute/guarantee language ('100%', 'guaranteed', "
                "'never fails') in mandates/copy — Laura blocks it as a flag.")
    if "scope-creep" in lowered or "scope creep" in lowered:
        return ("correction",
                "Keep mandates scoped to one coherent domain; scope-creep "
                "triggers a Laura flag.")
    if "uncovered" in lowered or "gap" in lowered:
        return ("gap",
                "When a real signal falls outside standing coverage, spin a "
                "focused daughter rather than stretching an existing center.")
    if kind == "success":
        return ("success",
                "Laura-passed offerings share: honest hedge-language, one "
                "clear mandate, real demand evidence. Reuse that shape.")
    # default: keep a trimmed version
    return (kind, raw[:160])


def publish_to_global(state, lesson_rec):
    """Add a generalised version of this lesson to the shared cross-firm pool."""
    ff = state.setdefault(_FOUNDATION_KEY, {})
    g = ff.setdefault(_GLOBAL_KEY, {
        "lessons": [],
        "published_by": {},
        "absorbed_by": {},
    })
    gkind, glesson = _generalise(lesson_rec)
    entry = {
        "ts": int(time.time()),
        "kind": gkind,
        "lesson": glesson,
        "from": lesson_rec.get("origin") or lesson_rec.get("meta", {}).get("cand") or "?",
    }
    # de-dup: skip if an identical generalised lesson already in the pool
    for e in g["lessons"]:
        if e["lesson"] == glesson and e["kind"] == gkind:
            e["ts"] = entry["ts"]  # refresh
            return
    g["lessons"].append(entry)
    if len(g["lessons"]) > _MAX_GLOBAL:
        g["lessons"] = g["lessons"][-_MAX_GLOBAL:]
    src = lesson_rec.get("origin") or "?"
    g["published_by"][src] = g["published_by"].get(src, 0) + 1


def absorb_global(state, slug):
    """A firm reads the shared pool and adopts lessons it has NOT yet learned.

    Returns the number of new lessons absorbed (so reflect_all can report
    cross-firm transfer activity). Absorbed lessons are appended to the
    firm's own memory, tagged learned_from: cross_firm, so we never pretend
    the firm discovered it itself.
    """
    ff = state.get(_FOUNDATION_KEY, {})
    g = ff.get(_GLOBAL_KEY)
    rec = ff.get(slug)
    if not g or not rec:
        return 0
    pool = g.get("lessons", [])
    if not pool:
        return 0
    # lessons this firm already knows (by lesson text) — avoid re-absorbing
    known = {l.get("lesson") for l in rec.get("lessons", [])}
    absorbed = 0
    for e in pool:
        if e.get("from") == slug:
            continue  # don't absorb your own lesson back
        if e["lesson"] in known:
            continue
        rec["lessons"].append({
            "ts": int(time.time()),
            "kind": e["kind"],
            "context": f"cross-firm transfer from {e.get('from')}",
            "lesson": e["lesson"],
            "meta": {"learned_from": "cross_firm", "source_firm": e.get("from")},
            "applied": False,
            "origin": f"cross_firm:{e.get('from')}",
        })
        known.add(e["lesson"])
        absorbed += 1
        # a correction absorbed from a peer still strengthens the firm
        if e["kind"] == "correction":
            rec["reflection_score"] = round(
                min(0.98, rec.get("reflection_score", _INITIAL_SCORE) + 0.02), 3)
    # bound
    if len(rec["lessons"]) > _MAX_LESSONS:
        rec["lessons"] = rec["lessons"][-_MAX_LESSONS:]
    # track absorption stats on the global record
    g.setdefault("absorbed_by", {})[slug] = g["absorbed_by"].get(slug, 0) + absorbed
    return absorbed


def learn_from_laura_block(state, slug, cand, flags):
    """Laura's gate blocked a candidate for this firm. Capture WHY so the firm
    can stop repeating the mistake.

    flags: list of {lens, severity, span, message} dicts from Laura.
    """
    reasons = []
    for f in (flags or []):
        msg = (f.get("message") or "").strip()
        lens = f.get("lens") or f.get("source") or "?"
        if msg:
            reasons.append(f"[{lens}] {msg}")
    why = "; ".join(reasons) if reasons else "Laura flagged unspecified issue"
    # A 'correction' lesson: the firm proposed something Laura rejected.
    record_lesson(
        state, slug, "correction",
        context=f"spawn candidate '{cand.get('slug')}' blocked by Laura",
        lesson=f"Laura blocked: {why}. Avoid absolute/guarantee language and "
               f"scope-creep in future mandates.",
        meta={"cand": cand.get("slug"), "flags": len(flags or [])},
        gap="honest-copy-discipline",
    )
    # mark the correction as something to learn from
    rec = ensure_foundation(state, slug)
    rec["corrections_applied"] += 1


def learn_from_lead_failure(state, slug, lead):
    """A real lead arrived but did not mature into a resolved debate/offering.
    Capture it as a 'failure' lesson so the firm notices thin demand signals.
    """
    kind = lead.get("kind", "?")
    record_lesson(
        state, slug, "failure",
        context=f"lead kind='{kind}' did not advance pipeline",
        lesson=f"Lead of type '{kind}' arrived but produced no resolved "
               f"deliberation — demand signal was real but unconverted.",
        meta={"lead_kind": kind, "qhash": lead.get("question_hash", "")[:12]},
    )


def learn_from_launch(state, slug, cand):
    """A staged offering cleared Laura + launched. Success lesson — the firm
    shipped something that passed every gate.
    """
    record_lesson(
        state, slug, "success",
        context=f"offering '{cand.get('slug')}' launched (Laura-passed)",
        lesson="Shipped a Laura-approved offering — the gap thesis + honest "
               "copy held up at the FINAL gate.",
        meta={"cand": cand.get("slug")},
    )
    ensure_foundation(state, slug)["launches"] += 1


def capability_gaps(state, slug):
    """Return the list of capability gaps this firm currently knows it has."""
    rec = state.get(_FOUNDATION_KEY, {}).get(slug)
    if not rec:
        return []
    return list(rec.get("capabilities", {}).get("gaps", []))


def reflect_all(state):
    """Daily autonomous reflection for EVERY firm.

    For each firm:
      * count lessons by kind,
      * mark 'correction'/'success' lessons as applied once the firm has
        demonstrably acted (we treat a later successful launch, or a later
        staged candidate that Laura passed, as evidence of learning),
      * raise reflection_score when the firm shows learning maturity
        (has corrections AND later successes), lower it slightly when it
        only ever fails (stuck) — but never below the floor,
      * prune duplicate gaps.

    Also SEEDS a foundation record for every standing center that does not
    have one yet, so all firms start with a (modest) foundation immediately
    rather than only after an event fires a hook.

    Returns a summary dict {firms: n, avg_score: float, lessons_total: int}.
    """
    # seed foundations for all standing centers (idempotent).
    # CENTER_SLUGS is the full 51-center registry; state['centers'] only
    # holds per-center version metadata for some, so iterate the registry.
    try:
        from runtime import CENTER_SLUGS
        for slug in list(CENTER_SLUGS):
            ensure_foundation(state, slug)
    except Exception:
        for slug in list(state.get("centers", {}).keys()):
            ensure_foundation(state, slug)
    # ── seed the immutable RFI-IRFOS core directive + its first lesson ───────
    try:
        ensure_core_directive(state)
        seed_core_lesson(state)
    except Exception as _e:
        print(f"[core] directive seed failed: {_e}", flush=True)
    ff = state.get(_FOUNDATION_KEY, {})
    if not ff:
        return {"firms": 0, "avg_score": 0.0, "lessons_total": 0}
    # ── cross-firm transfer: every firm absorbs the shared pool FIRST, so
    #    reflect_all counts the transferred lessons in its totals. ──────────
    total_absorbed = 0
    for slug in list(ff.keys()):
        if slug in (_GLOBAL_KEY, _CORE_KEY):
            continue
        try:
            total_absorbed += absorb_global(state, slug)
        except Exception as _e:
            print(f"[learning] absorb_global failed for {slug}: {_e}", flush=True)
    total_lessons = 0
    scores = []
    for slug, rec in ff.items():
        if slug in (_GLOBAL_KEY, _CORE_KEY):
            continue
        lessons = rec.get("lessons", [])
        total_lessons += len(lessons)
        n_corr = sum(1 for l in lessons if l["kind"] == "correction")
        n_succ = sum(1 for l in lessons if l["kind"] == "success")
        n_fail = sum(1 for l in lessons if l["kind"] == "failure")
        # Learning maturity: did the firm turn a block into a later success?
        matured = n_corr > 0 and n_succ > 0
        # Score dynamics — bounded [0.2, 0.98].
        score = rec.get("reflection_score", _INITIAL_SCORE)
        if matured:
            score = min(0.98, score + 0.06)  # learned from a block -> stronger
        elif n_succ > 0:
            score = min(0.98, score + 0.03)
        elif n_fail > 0 and n_corr == 0:
            score = max(0.2, score - 0.02)  # stuck failing, no self-correction
        rec["reflection_score"] = round(score, 3)
        rec["last_reflection"] = int(time.time())
        # mark applied: a correction is 'applied' once a success followed it
        if n_succ > 0:
            for l in lessons:
                if l["kind"] in ("correction", "failure"):
                    l["applied"] = True
        # prune duplicate gaps (keep last 10)
        gaps = rec.get("capabilities", {}).get("gaps", [])
        rec["capabilities"]["gaps"] = gaps[-10:]
        scores.append(score)
    avg = round(sum(scores) / len(scores), 3) if scores else 0.0
    # global pool stats for visibility (no UI — just the cron summary)
    g = ff.get(_GLOBAL_KEY, {})
    return {
        "firms": len(ff) - (1 if _GLOBAL_KEY in ff else 0),
        "avg_score": avg,
        "lessons_total": total_lessons,
        "cross_firm_absorbed": total_absorbed,
        "global_pool_size": len(g.get("lessons", [])),
        "published_by": g.get("published_by", {}),
        "absorbed_by": g.get("absorbed_by", {}),
    }


def foundation_report(state, slug=None):
    """Read-only snapshot for logging/debug (NOT for UI)."""
    ff = state.get(_FOUNDATION_KEY, {})
    if slug:
        rec = ff.get(slug)
        return dict(rec) if rec else None
    return {s: {"score": r.get("reflection_score"), "lessons": len(r.get("lessons", [])),
               "launches": r.get("launches", 0),
               "corrections": r.get("corrections_applied", 0)}
            for s, r in ff.items()}


# ---------------------------------------------------------------------------
# Active self-correction: a firm re-reads what it (and its peers) learned and
# DE-FANGS a candidate's copy BEFORE Laura sees it. This is the "apply" half of
# learning — not just remembering the mistake, but refusing to repeat it.
# Deterministic, no LLM call: pattern-matched against known lesson shapes.
# ---------------------------------------------------------------------------

# (phrase, replacement) pairs — consistent with the RFI-IRFOS 90/10 directive.
# We never claim 100%; we state 90% confidence + 10% priced-in risk.
_SELF_CORRECT_PATTERNS = [
    (r"\b100\s*%", "90% (rest: 10% priced-in risk)"),
    (r"\bguaranteed\b", "designed"),
    (r"\bnever fails?\b", "is built to be resilient (10% failure priced in)"),
    (r"\balways works\b", "typically holds up"),
    (r"\bzero risk\b", "low, managed risk (10% still assumed)"),
    (r"\bno risk\b", "low, managed risk (10% still assumed)"),
    (r"\b(we cover|handles?) (everything|all domains)\b",
     r"\1 our focused mandate"),
]

import re as _re


def _collect_known_mistakes(state, slug):
    """Return the set of mistake 'shapes' this firm knows (own + cross-firm)."""
    ff = state.get(_FOUNDATION_KEY, {})
    rec = ff.get(slug)
    known = set()
    if rec:
        for l in rec.get("lessons", []):
            if l.get("kind") == "correction":
                known.add(l.get("lesson", "")[:60])
    g = ff.get(_GLOBAL_KEY)
    if g:
        for e in g.get("lessons", []):
            if e.get("kind") == "correction":
                known.add(e.get("lesson", "")[:60])
    return known


def self_review(state, slug, mandate):
    """Pre-Laura self-correction. Returns (corrected_mandate, changed: bool,
    notes: [str]).

    If the mandate contains a phrase the firm (or a peer) already got blocked
    for, rewrite it to the honest hedge BEFORE Laura flags it. This is the firm
    applying its own memory — autonomy in action, not just logging.
    """
    mistakes = _collect_known_mistakes(state, slug)
    if not mistakes:
        return mandate, False, []
    corrected = mandate
    notes = []
    for pat, repl in _SELF_CORRECT_PATTERNS:
        if _re.search(pat, corrected, _re.IGNORECASE):
            corrected = _re.sub(pat, repl, corrected, flags=_re.IGNORECASE)
            notes.append(f"de-fanged '{pat}' -> '{repl}' (learned mistake)")
    changed = corrected != mandate
    return corrected, changed, notes


def apply_self_correction(state, slug, cand):
    """Mutate a candidate's mandate in-place if a known mistake is present.
    Records a 'correction' lesson of kind 'self_fixed' so we can see the firm
    caught itself. Returns notes list (empty if nothing changed)."""
    mandate = cand.get("mandate", "")
    if not mandate:
        return []
    corrected, changed, notes = self_review(state, slug, mandate)
    if changed:
        cand["mandate"] = corrected
        rec = ensure_foundation(state, slug)
        rec["lessons"].append({
            "ts": int(time.time()),
            "kind": "self_fixed",
            "context": f"candidate '{cand.get('slug')}' self-corrected pre-Laura",
            "lesson": "Firm caught its own known mistake before Laura flagged it.",
            "meta": {"notes": notes, "learned_from": "self_review"},
            "applied": True,
            "origin": slug,
        })
        if len(rec["lessons"]) > _MAX_LESSONS:
            rec["lessons"] = rec["lessons"][-_MAX_LESSONS:]
        rec["reflection_score"] = round(
            min(0.98, rec.get("reflection_score", _INITIAL_SCORE) + 0.03), 3)
    return notes
