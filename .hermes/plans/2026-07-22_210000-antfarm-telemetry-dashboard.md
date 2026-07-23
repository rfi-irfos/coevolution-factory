# Ant-Farm Telemetry Dashboard (Hardcore BI) + Per-Team Command Channel — Implementation Plan

> **For Hermes:** Implement this plan task-by-task by dispatching a fresh subagent via the `delegate_task` tool.

**Goal:** Build a single high-grade Business-Intelligence telemetry view (Palantir-grade, calm, dense, no "toy" visuals) that shows EVERY agent across EVERY firm live — what each is doing (developing / discussing / improving / idle), grouped by firm as crisp tiles with real KPIs — PLUS a direct command console on every firm tile where the Board can type anything and push it straight to that firm's CEO/team (one-directional Board→CEO→Teamleads), reusing the existing `/api/board/directive` channel.

**Architecture:** Extend job records with an `activity_kind` field (develop/discuss/improve/directive/idle) classified by job TYPE (not free text). Add a batched `/api/agent-grid` endpoint aggregating per firm: roster members (Teamleads + Experts) stamped with the firm's live `activity_kind`, real KPIs (sessions, revenue, leads, problems, status, latency if present), and open board-directive count. Add a new `/observatory` successor page `/antfarm` rendered as a serious BI console: a top KPI strip, a dense firm-grid of telemetry tiles (each with agent rows, live activity LEDs, and a per-team command input that POSTs to `/api/board/directive`), polling live every ~6s. The public landing honeycomb and cashflow `/observatory` stay untouched — this is the Board's internal ops console. No new dependencies.

**Tech Stack:** Python 3, aiohttp, existing `state.json` (`state["jobs"]`, `state["board_directives"]`, `state["usage"]`, `state["leads"]`), existing `_live_stats_for` / `_active_job_for` / `_revenue_for` / `_leads_for` / `_problems_for`, `CENTERS_META[slug]["roster"]` (prior plan), aiohttp server-side HTML + vanilla JS polling `fetch('/api/agent-grid')` and `fetch('/api/board/directive', {method:'POST'})`. Calm dark theme, system/monospace type, CSS grid (no canvas).

---

## Current context (confirmed by reading the code)

- `live_grid` (runtime.py:1830) → `{slug: _live_stats_for(s)}` for ALL centers (batched source).
- `_live_stats_for(slug)` (runtime.py:604) → `{slug, status, sessions, revenue_eur, leads, problems, active_job}`. `active_job` = `_active_job_for` (runtime.py:586) → `{status, created}`. No `activity_kind` yet.
- Job records built in: `center_session` (~928), `debate_session` (~1181), `spawn_session` (~1370), `propose_session` (~1358), `evolve_handler` (~1440), `board_directive_handler_logic` (~966, already `"priority":"board"`). Each writes `state["jobs"][run_id] = {center, status, created, text, panel, result, error, ...}`.
- `CENTERS_META[slug]["roster"]` (prior plan) = `{"departments":[{"id","name","lead":{"agent","name","role"},"experts":[{"agent","name","role"}]}]}`.
- `/api/board/directive` already exists (runtime.py:3478) — POST, `require_operator`, writes `state["board_directives"][center]`, spawns a `priority:"board"` job. This is the per-team command channel's backend.
- `board_status` (GET) exists. We will surface `board_directives[center]` ack state per tile.
- Routes at runtime.py:3454-3483. We add `app.router.add_get("/antfarm", antfarm_page)` + `app.router.add_get("/api/agent-grid", agent_grid)`. (`/api/board/directive` already registered.)
- `get_center_status`, `ICON_COLORS`, `ICON_BY_SLUG` available for tile accents.

---

## Task 1: Add `activity_kind` to every job record

**Objective:** Stamp each job with a stable `kind` so telemetry classifies activity without parsing free text.

**Files:**
- Modify: `factory/runtime.py` (job-dict literals ~928, ~1181, ~1370, ~1358, ~1440, ~966; extend `_active_job_for` ~601)

**Step 1: Write failing test** — `factory/tests/test_activity_kind.py`
```python
import runtime

def _seed(slug, kind):
    runtime.state.setdefault("jobs", {})["run_" + kind] = {
        "center": slug, "status": "running", "created": 1,
        "text": "x", "panel": ["a"], "result": None, "error": None, "kind": kind}

def test_kind_passthrough():
    _seed("gdpr-guard", "discuss")
    assert runtime.state["jobs"]["run_discuss"]["kind"] == "discuss"

def test_active_job_exposes_kind():
    _seed("gdpr-guard", "develop")
    aj = runtime._active_job_for("gdpr-guard")
    assert aj is not None and aj.get("kind") == "develop"
```

**Step 2: Run** `cd /home/eri-irfos/projects/coevolution-factory/factory && python3 -m pytest tests/test_activity_kind.py -v` → FAIL (no `kind`).

**Step 3: Implement** — add `"kind": "<type>"` to each job literal: `center_session`→`"discuss"`, `debate_session`→`"discuss"`, `spawn_session`→`"develop"`, `propose_session`→`"improve"`, `evolve_handler`→`"improve"`, `board_directive_handler_logic`→`"directive"`. Extend `_active_job_for` return:
```python
    return {"status": j.get("status"), "created": j.get("created"),
            "kind": j.get("kind", "discuss")}
```

**Step 4: Run** → PASS.

**Step 5: Commit**
```bash
git -C /home/eri-irfos/projects/coevolution-factory add factory/runtime.py factory/tests/test_activity_kind.py
git -C /home/eri-irfos/projects/coevolution-factory commit -m "feat(jobs): stamp activity_kind by type for telemetry"
```

---

## Task 2: `/api/agent-grid` aggregation (real KPIs + roster + directives)

**Objective:** One batched endpoint returning per firm: real KPIs, roster agents stamped with live `activity_kind`, and open board-directive count + last directive status.

**Files:**
- Modify: `factory/runtime.py` (new `build_agent_grid` + `agent_grid` after `live_grid` ~1834; register route ~3462)

**Step 1: Write failing test** — `factory/tests/test_agent_grid.py`
```python
import runtime, catalog

def test_grid_shape():
    g = runtime.build_agent_grid()
    assert set(g["firms"].keys()) == set(catalog.CENTERS_META.keys())
    f = g["firms"]["gdpr-guard"]
    for k in ("name", "status", "kind", "agents", "open_directives",
              "sessions", "revenue_eur", "leads", "problems", "accent"):
        assert k in f, k
    a = f["agents"][0]
    assert {"name", "role", "kind"} <= set(a.keys())
    assert a["kind"] in ("develop", "discuss", "improve", "directive", "idle")

def test_grid_kind_from_job():
    runtime.state.setdefault("jobs", {})["r1"] = {
        "center": "gdpr-guard", "status": "running", "created": 9,
        "text": "x", "panel": ["a"], "kind": "develop"}
    kinds = {a["kind"] for a in runtime.build_agent_grid()["firms"]["gdpr-guard"]["agents"]}
    assert "develop" in kinds
```

**Step 2: Run** → FAIL (`build_agent_grid` missing).

**Step 3: Implement**
```python
def build_agent_grid():
    firms = {}
    for slug, m in CENTERS_META.items():
        stats = _live_stats_for(slug)
        aj = _active_job_for(slug)
        kind = aj["kind"] if aj else "idle"
        roster = m.get("roster", {})
        agents = []
        for dep in roster.get("departments", []):
            lead = dep.get("lead") or {}
            if lead.get("agent"):
                agents.append({"name": lead.get("name") or lead.get("agent"),
                               "agent": lead.get("agent"), "role": "lead", "kind": kind})
            for ex in dep.get("experts", []):
                agents.append({"name": ex.get("name") or ex.get("agent"),
                               "agent": ex.get("agent"), "role": "expert", "kind": kind})
        bdirs = runtime.state.get("board_directives", {}).get(slug, [])
        open_d = [d for d in bdirs if d.get("status") in ("routed_to_ceo", "in_review")]
        last_d = bdirs[-1] if bdirs else None
        firms[slug] = {
            "name": m.get("name"), "status": stats["status"], "kind": kind,
            "agents": agents, "open_directives": len(open_d),
            "last_directive": (last_d["directive"] if last_d else None),
            "sessions": stats["sessions"], "revenue_eur": stats["revenue_eur"],
            "leads": stats["leads"], "problems": stats["problems"],
            "accent": ICON_COLORS.get(ICON_BY_SLUG.get(slug, "shield"), "#36d6a0"),
        }
    return {"firms": firms, "generated": int(time.time())}

async def agent_grid(request):
    return web.json_response(build_agent_grid())
```
Register: `app.router.add_get("/api/agent-grid", agent_grid)`.

**Step 4: Run** → PASS.

**Step 5: Commit**
```bash
git -C /home/eri-irfos/projects/coevolution-factory add factory/runtime.py factory/tests/test_agent_grid.py
git -C /home/eri-irfos/projects/coevolution-factory commit -m "feat(api): /api/agent-grid batched BI telemetry"
```

---

## Task 3: `/antfarm` BI console — server-rendered shell

**Objective:** A serious Board ops console: top KPI strip, dense firm-grid of telemetry tiles (each with agent rows, activity LED, real KPIs, open-directive badge, and a per-team command input). Server-rendered (no-JS fallback) with live-patch hooks.

**Files:**
- Modify: `factory/runtime.py` (new `ANTFARM_TR` near `CENTER_PAGE_TR` ~1853; `build_antfarm_html` + `antfarm_page` after `observatory`; register route ~3460)

**Step 1: Write failing test**
```python
def test_antfarm_html():
    html = runtime.build_antfarm_html("en")
    assert "gdpr-guard" in html and "data-kind=" in html
    assert 'class="cmd"' in html          # per-team command console present
    assert "/api/board/directive" in html  # console posts here
```

**Step 2: Run** → FAIL (`build_antfarm_html` missing).

**Step 3: Implement** — add `ANTFARM_TR` (en/de) with: title, subtitle, kind labels (develop/discuss/improve/directive/idle), `cmd_placeholder` ("Directive to this team…"), `cmd_send` ("Send"), `cmd_sent` ("Directive routed to CEO"), column headers (Agents, Sessions, Revenue, Leads, Problems).
Add `build_antfarm_html(lang)`:
```python
def _agent_row(a, t):
    label = t.get(a["kind"], a["kind"])
    role_tag = "lead" if a["role"] == "lead" else "exp"
    return (f'<div class="arow" data-kind="{a["kind"]}">'
            f'<span class="aled"></span>'
            f'<span class="aname">{html.escape(a["name"])}'
            f'<span class="arole">{role_tag}</span></span>'
            f'<span class="akind">{html.escape(label)}</span></div>')

def build_antfarm_html(lang="en"):
    t = ANTFARM_TR.get(lang, ANTFARM_TR["en"])
    g = build_agent_grid()
    tiles = []
    for slug, f in g["firms"].items():
        rows = "".join(_agent_row(a, t) for a in f["agents"])
        bd = (f'<span class="bd" title="open board directive">▲{f["open_directives"]}</span>'
              if f["open_directives"] else "")
        tiles.append(
            f'<section class="ftile" data-slug="{slug}" data-kind="{f["kind"]}" style="--ac:{f["accent"]}">'
            f'<header class="fhead"><span class="fname">{html.escape(f["name"])}</span>{bd}'
            f'<span class="fstatus">{html.escape(f["status"])}</span></header>'
            f'<div class="kpis">'
            f'<div class="kpi"><b>{f["sessions"]}</b><span>sessions</span></div>'
            f'<div class="kpi"><b>€{f["revenue_eur"]:.0f}</b><span>revenue</span></div>'
            f'<div class="kpi"><b>{f["leads"]}</b><span>leads</span></div>'
            f'<div class="kpi"><b>{f["problems"]}</b><span>problems</span></div></div>'
            f'<div class="arows">{rows}</div>'
            f'<form class="cmd" data-slug="{slug}" onsubmit="return sendCmd(event,this)">'
            f'<input class="cmdin" name="directive" placeholder="{html.escape(t["cmd_placeholder"])}" '
            f'autocomplete="off" maxlength="500">'
            f'<button class="cmdsend" type="submit">{html.escape(t["cmd_send"])}</button>'
            f'<span class="cmdok"></span></form>'
            f'</section>')
    return ("<!doctype html><html lang=\"" + lang + "\"><head><meta charset=utf-8>"
            "<meta name=viewport content=\"width=device-width,initial-scale=1\">"
            "<title>" + html.escape(t["title"]) + "</title><style>" + _ANTFARM_CSS +
            "</style></head><body>"
            "<header class=\"topbar\"><h1>" + html.escape(t["title"]) +
            "</h1><div class=\"sub\">" + html.escape(t["subtitle"]) + "</div>"
            "<div class=\"legend\">"
            "<span class=\"lg k-develop\">● " + t["develop"] + "</span>"
            "<span class=\"lg k-discuss\">● " + t["discuss"] + "</span>"
            "<span class=\"lg k-improve\">● " + t["improve"] + "</span>"
            "<span class=\"lg k-directive\">● " + t["directive"] + "</span>"
            "<span class=\"lg k-idle\">● " + t["idle"] + "</span></div></header>"
            "<main class=\"farm\">" + "".join(tiles) + "</main>"
            "<script>" + _ANTFARM_JS + "</script></body></html>")
```
Add `antfarm_page`:
```python
async def antfarm_page(request):
    lang = request.query.get("lang", "en")
    if lang not in ("en", "de"): lang = "en"
    return web.Response(text=build_antfarm_html(lang), content_type="text/html")
```
Register: `app.router.add_get("/antfarm", antfarm_page)` (after `/observatory`).

**Step 4: Run** → PASS.

**Step 5: Commit**
```bash
git -C /home/eri-irfos/projects/coevolution-factory add factory/runtime.py factory/tests/test_agent_grid.py
git -C /home/eri-irfos/projects/coevolution-factory commit -m "feat(ui): /antfarm BI console shell with per-team command channel"
```

---

## Task 4: Hardcore BI CSS + live-poll + command POST JS

**Objective:** Style as a calm, dense, Palantir-grade BI console (NOT toy/ant visuals). Patch tiles live every 6s. Wire the per-team command input to `POST /api/board/directive` and show ack.

**Files:**
- Modify: `factory/runtime.py` (add `_ANTFARM_CSS` + `_ANTFARM_JS` module constants)

**Step 1: Write failing test**
```python
def test_css_js_present():
    html = runtime.build_antfarm_html("de")
    assert ".ftile" in html and 'onsubmit="return sendCmd' in html
    assert "fetch('/api/agent-grid')" in html or 'fetch("/api/agent-grid")' in html
    assert "/api/board/directive" in html
```

**Step 2: Run** → FAIL (constants undefined).

**Step 3: Implement**
```python
_ANTFARM_CSS = """
:root{--bg:#070a0f;--panel:#0d1219;--panel2:#111824;--line:#1c2733;--txt:#e6edf3;
 --mut:#8b98a9;--develop:#3b82f6;--discuss:#36d6a0;--improve:#f59e0b;
 --directive:#a855f7;--idle:#475569;--ok:#36d6a0;--warn:#f0883e;--bad:#f85c5c}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--txt);
 font:13px/1.45 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.topbar{padding:14px 22px;border-bottom:1px solid var(--line);position:sticky;top:0;
 background:#070a0feE;z-index:10;display:flex;align-items:baseline;gap:16px;flex-wrap:wrap}
.topbar h1{margin:0;font-size:16px;font-weight:700;letter-spacing:.02em}
.sub{color:var(--mut);font-size:12px}
.legend{margin-left:auto;display:flex;gap:14px;font-size:11px;color:var(--mut)}
.lg.k-develop{color:var(--develop)}.lg.k-discuss{color:var(--discuss)}
.lg.k-improve{color:var(--improve)}.lg.k-directive{color:var(--directive)}
.lg.k-idle{color:var(--idle)}
.farm{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));
 gap:12px;padding:16px 22px}
.ftile{background:var(--panel);border:1px solid var(--line);border-radius:10px;
 border-top:2px solid var(--ac);padding:12px 14px;display:flex;flex-direction:column;gap:10px}
.fhead{display:flex;align-items:center;gap:8px}
.fname{font-weight:700;font-size:13px;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.fstatus{font-size:10px;color:var(--mut);border:1px solid var(--line);border-radius:4px;padding:1px 6px}
.bd{color:var(--directive);font-size:11px;font-weight:700}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}
.kpi{background:var(--panel2);border:1px solid var(--line);border-radius:6px;padding:6px 8px}
.kpi b{display:block;font-size:14px;font-weight:700}
.kpi span{font-size:10px;color:var(--mut)}
.arows{display:flex;flex-direction:column;gap:3px;border-top:1px solid var(--line);padding-top:8px}
.arow{display:flex;align-items:center;gap:8px;font-size:12px}
.aled{width:7px;height:7px;border-radius:50%;background:var(--idle);flex:none}
.arow[data-kind=develop] .aled{background:var(--develop)}
.arow[data-kind=discuss] .aled{background:var(--discuss)}
.arow[data-kind=improve] .aled{background:var(--improve)}
.arow[data-kind=directive] .aled{background:var(--directive)}
.aname{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.arole{font-size:9px;color:var(--mut);border:1px solid var(--line);border-radius:3px;padding:0 4px;margin-left:6px}
.akind{font-size:10px;color:var(--mut)}
.cmd{display:flex;gap:6px;margin-top:4px;border-top:1px solid var(--line);padding-top:8px}
.cmdin{flex:1;background:#060910;border:1px solid var(--line);border-radius:6px;
 color:var(--txt);padding:6px 9px;font:inherit;font-size:12px}
.cmdin:focus{outline:none;border-color:var(--ac)}
.cmdsend{background:var(--ac);color:#04140d;border:none;border-radius:6px;
 font-weight:700;padding:6px 12px;cursor:pointer;font:inherit;font-size:12px}
.cmdok{font-size:11px;color:var(--ok);align-self:center;min-width:60px}
"""
_ANTFARM_JS = """
function paint(g){
  Object.keys(g.firms).forEach(function(slug){
    var ft=document.querySelector('.ftile[data-slug=\"'+slug+'\"]'); if(!ft)return;
    var f=g.firms[slug]; ft.setAttribute('data-kind',f.kind);
    f.agents.forEach(function(a,i){var r=ft.querySelectorAll('.arow')[i]; if(r)r.setAttribute('data-kind',a.kind);});
    var bd=ft.querySelector('.bd'); if(bd)bd.textContent=f.open_directives?('▲'+f.open_directives):'';
  });
}
function poll(){fetch('/api/agent-grid').then(function(r){return r.json();}).then(paint).catch(function(){});}
function sendCmd(ev,form){
  ev.preventDefault();
  var slug=form.getAttribute('data-slug');
  var inp=form.querySelector('.cmdin'); var ok=form.querySelector('.cmdok');
  var text=inp.value.trim(); if(!text)return false;
  ok.textContent='…'; ok.style.color='var(--mut)';
  fetch('/api/board/directive?center='+encodeURIComponent(slug),
    {method:'POST',headers:{'Content-Type':'application/json'},
     body:JSON.stringify({center:slug,directive:text})})
   .then(function(r){return r.json();})
   .then(function(j){ok.textContent=j.directive_id?'✓ routed':'✓';ok.style.color='var(--ok)';inp.value='';})
   .catch(function(){ok.textContent='✗';ok.style.color='var(--bad)';});
  return false;
}
poll(); setInterval(poll,6000);
"""
```

**Step 4: Run** `python3 -m pytest tests/test_agent_grid.py -v` → PASS; lint JS:
```bash
cd /home/eri-irfos/projects/coevolution-factory/factory
python3 -c "import runtime;open('/tmp/af.js','w').write(runtime._ANTFARM_JS)"
node --check /tmp/af.js && echo "JS OK"
```

**Step 5: Commit**
```bash
git -C /home/eri-irfos/projects/coevolution-factory add factory/runtime.py factory/tests/test_agent_grid.py
git -C /home/eri-irfos/projects/coevolution-factory commit -m "feat(ui): ant-farm BI CSS + live poll + per-team command POST"
```

---

## Task 5: Pre-flight + push + deploy

**Objective:** Prove render + JS parse + endpoint completeness, then ship.

**Step 1: Pre-flight**
```bash
cd /home/eri-irfos/projects/coevolution-factory/factory
python3 - <<'PY'
import sys; sys.path.insert(0,'.')
import runtime, catalog
g = runtime.build_agent_grid()
assert set(g["firms"].keys()) == set(catalog.CENTERS_META.keys())
runtime.state.setdefault("jobs",{})["r1"]={"center":"gdpr-guard","status":"running","created":5,"text":"x","panel":["a"],"kind":"develop"}
assert "develop" in {a["kind"] for a in runtime.build_agent_grid()["firms"]["gdpr-guard"]["agents"]}
h = runtime.build_antfarm_html("de")
assert "Ameisenhaufen" in h and "gdpr-guard" in h and 'class="cmd"' in h
assert "/api/board/directive" in h
print("PREFLIGHT OK | firms:", len(g["firms"]))
PY
python3 -m pytest tests/ -q
```
Expected: `PREFLIGHT OK`, tests pass.

**Step 2: Push**
```bash
cd /home/eri-irfos/projects/coevolution-factory
git add -A && git commit -m "test: ant-farm BI + command channel coverage" || echo "nothing"
git push origin master
```

**Step 3: Deploy**
```bash
cd /home/eri-irfos/projects/coevolution-factory/factory
export PATH="$HOME/.fly/bin:$PATH"
APP=coevolution-factory-sparkling-mountain-1802
for i in $(seq 1 20); do
  out=$(fly deploy -a "$APP" -c fly.toml --remote-only 2>&1)
  echo "$out" | tail -1
  if echo "$out" | grep -qiE "Visit your newly deployed app|deployed|complete"; then echo "DEPLOY_OK attempt $i"; break; fi
  sleep 30
done
```

**Step 4: Live smoke**
```bash
python3 - <<'PY'
import urllib.request, json
BASE="https://coevolution-factory-sparkling-mountain-1802.fly.dev"
html=urllib.request.urlopen(f"{BASE}/antfarm?lang=de", timeout=25).read().decode()
print("title:", "Ameisenhaufen" in html, "| cmd consoles:", html.count('class="cmd"'))
g=json.loads(urllib.request.urlopen(f"{BASE}/api/agent-grid", timeout=25).read())
print("firms:", len(g["firms"]), "| sample kpis:", g["firms"]["gdpr-guard"]["sessions"], g["firms"]["gdpr-guard"]["revenue_eur"])
# send a directive via the command channel
import urllib.request
req=urllib.request.Request(f"{BASE}/api/board/directive?center=gdpr-guard",
  data=json.dumps({"center":"gdpr-guard","directive":"Prioritize DPIA turnaround"}).encode(),
  headers={"Content-Type":"application/json"}, method="POST")
try:
    r=urllib.request.urlopen(req, timeout=25); print("directive POST:", r.status, json.loads(r.read()).get("directive_id"))
except Exception as e: print("directive POST (auth expected if key-gated):", e)
PY
```
Expected: `title: True`, `cmd consoles: >0`, `firms: 50`, sample KPIs printed; directive POST either succeeds (200 + id) or returns 401/403 if `require_operator` key is enforced (that is correct — the console in-browser sends with credentials).

---

## Risks / tradeoffs / open questions

- **Look:** deliberately Palantir-grade — monospace, dense grid, calm dark, no motion beyond a 6s data refresh and static status LEDs. No "ant"/toy metaphors in the UI (the name is internal only).
- **Standing-team semantics:** a firm's `active_job` makes ALL its roster agents show the same `kind` (the panel convenes as a standing team). Honest; per-agent granularity would need jobs to name specific agents — out of scope (YAGNI).
- **activity_kind by job TYPE, not text** — no fabricated classification.
- **Per-team command channel = existing `/api/board/directive`** (one-directional Board→CEO→Teamleads, `priority:board`). The console POSTs exactly that. If `require_operator` enforces a key, the browser console must send credentials — verify the live POST returns 200 (or 401 if key-gated; add credential handling in a follow-up if needed).
- **Auth:** `/antfarm` is open like `/observatory` in this plan. If it must be Board-only, gate `antfarm_page` behind `require_operator` (follow-up).
- **Backward compat:** `"kind"` additive; `_active_job_for` gained a key, existing callers unaffected.
- **Agent display names** are slugs today (e.g. `legal-privacy`); human labels = follow-up enrichment of `derive_roster`.
- **Open question (non-blocking):** KPI `problems`/`revenue_eur` come from real `state` aggregates already used by `/observatory` — confirm they are non-zero in prod before treating the dashboard as "live cashflow truth" (they are real, not fabricated).
