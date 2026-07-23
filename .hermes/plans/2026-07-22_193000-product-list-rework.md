# Real Product List Rework — Implementation Plan

> **For Hermes:** Implement this plan task-by-task by dispatching a fresh subagent via the `delegate_task` tool.

**Goal:** Replace the self-evident "Was du bekommst" bullets and the prompt-style "Unsere Services" list in the center modal with ONE plain, honest list of ≥7 concrete products/deliverables per firm, drawn from each firm's real domain (not prompts, not "you get a finished result" filler).

**Architecture:** Add a `products` list to every center dict in `catalog.py` (7+ concrete deliverables each, plain-language, what the client RECEIVES). Render it in `center_card_html` as a single "Produkte & Leistungen" / "Products & Services" block. Delete the `whatyouget` block, the `servicelist` block, the `services_html` build, and the dead `use_cases` injection. Keep the green buy button (already fixed to "Anheuern · €X") and the KPI "Status" tile.

**Tech Stack:** Python 3 (server-rendered HTML f-string), no new deps. CSS inside the `page = f"""<style>...</style>"""` block. Deploy via `fly deploy`.

---

## Current context / why

- `runtime.py:2382-2391` renders two boxes: `what_you_get` (3 self-evident bullets: "a finished result", "by a team of experts", "in minutes") and `servicelist` (built from `c.get("use_cases")` — which are PROMPTS like "Do we need a DPIA...?", not products).
- User feedback (verbatim): "digitale produkte brauchen keinen prompt", "ein fertiges ergebnis schreibt man nicht raus — das erwartet jeder bei euro", "unsere services sind fragen... wer versteht das".
- Decision: both boxes go. One honest product list replaces them. Products are CONCRETE DELIVERABLES (e.g. "DPIA-Vorprüfung — wir sagen dir, ob dein Feature eine Folgenabschätzung braucht"), never questions, never self-evident filler.

## Data shape (confirmed)

- `catalog.py` `CENTERS` is a list; `meta[slug] = {"name", "domain", ...}` built at line ~379; full dict `c` accessed in `runtime.py` as `c['price']`, `c['panel']`, `c.get("use_cases")`.
- Each center dict has `value_prop` (one sentence) + `use_cases` (prompts — DO NOT use for the product list) + `icp_pain`.
- New field `products` = list of plain strings, each one concrete deliverable. 7+ per center.

---

## Task 1: Add `products` lists to catalog.py (all 51 centers)

**Objective:** Every center dict gets a `products` key with ≥7 concrete deliverables derived from its domain. No prompts, no "finished result" filler.

**Files:**
- Modify: `factory/catalog.py` (inside each center dict, alongside `value_prop`)

**Step 1: Author the 5 fully-specified example centers below (copy-paste exactly).** Insert `"products": [...]` right after each center's `"value_prop": "..."` line.

gdpr-guard (after line 449):
```python
  "products": [
    "DPIA-Vorprüfung — wir sagen dir, ob dein neues Feature eine Datenschutz-Folgenabschätzung braucht.",
    "Consent-Banner-Check — wir prüfen, ob deine Einwilligung rechtlich hält oder still vorab ankreuzt.",
    "Breach-Response-Clock — wir berechnen deine Meldefrist, wenn ein Laptop mit Kundendaten verloren geht.",
    "Auftragsverarbeitungs-Verträge — wir redlinen deine AVV mit jedem Subunternehmer.",
    "EU-Transfer-Fit — wir prüfen, ob dein US-Backend unter den Angemessenheitsbeschluss fällt.",
    "DSFA-Dokument — wir bauen die Folgenabschätzung, die der Audit verlangt.",
    "Privacy-Status quartalsweise — wir sagen dir, wo du gerade stehst, bevor der Inspector klingelt.",
    "Betroffenen-Auskunft — wir entwerfen die Antwort, die du auf Anfrage liefern musst."],
```

ai-act-guard (after line 456):
```python
  "products": [
    "High-Risk-Klassifikation — wir sagen, ob dein System unter Annex III fällt.",
    "Conformity-Roadmap — wir listen, was du für das CE-Zeichen schuldest.",
    "Model-Card-Bau — wir erstellen die Dokumentation, die die KI-Verordnung verlangt.",
    "Retrain-Check — wir prüfen, ob jede monatliche Neuschulung die Konformität re-triggert.",
    "Risiko-Management-System — wir bauen den Pflicht-Prozess um dein Modell herum.",
    "Human-Oversight-Konzept — wir definieren, wo ein Mensch entscheiden muss.",
    "Registrierungs-Pflicht — wir sagen, ob du im EU-Datenbank-Eintrag landest.",
    "Audit-Vorbereitung — wir simulieren den Konformitätstest, bevor die Behörde ihn macht."],
```

bias-fairness (after line 750):
```python
  "products": [
    "Disparate-Impact-Analyse — wir messen, ob dein Modell eine Gruppe systematisch benachteiligt.",
    "Fairness-Metriken-Report — wir liefern die Zahlen (Demographic Parity, Equalized Odds).",
    "Pre-Launch-Fairness-Audit — wir prüfen, bevor die Protokoll-Pflicht zur Gesetz wird.",
    "Feature-Bias-Check — wir finden die Proxy-Variable (z.B. Postleitzahl) für diskriminierende Muster.",
    "Model-Card — wir dokumentieren Trainingsdaten, Limitationen und Gruppeneffekte.",
    "Bias-Test-Suite — wir bauen die Tests, die dein CI künftig automatisch läuft.",
    "Schwachstellen-Mapping — wir zeigen, wo der nächste Audit ansetzen würde.",
    "Vendor-Fairness-Check — wir prüfen, ob ein gekauftes Modell deine Pflicht erfüllt."],
```

sox-controls (after line 463):
```python
  "products": [
    "Control-Gap-Analyse — wir sagen, welche SOX-Assertions dein Close nicht belegt.",
    "Walkthrough-Dry-Run — wir simulieren die Auditor-Begehung an deinen Buchungen.",
    "Segregation-of-Duties-Matrix — wir prüfen, ob sie durchgesetzt oder nur dokumentiert ist.",
    "Journal-Entry-Red-Flags — wir markieren die Buchungen, die ein Prüfer zuerst zieht.",
    "Acquisition-Scope-Check — wir finden fehlende Kontrollen nach dem Zukauf.",
    "Evidenz-Sammlung — wir legen die Nachweise, die der Auditor fordert, vorab bereit.",
    "Restatement-Risiko — wir benennen die Stellen, an denen du korrigieren müsstest.",
    "Quartals-Close-Review — wir sichten den Abschluss, bevor er gebucht wird."],
```

hipaa-check (after line 470):
```python
  "products": [
    "BAA-Lücke — wir prüfen, ob jedes PHI verarbeitende SDK einen Vertrag hat.",
    "Encryption-At-Rest-Check — wir sagen, wo deine Telehealth-Aufnahmen ungesichert liegen.",
    "De-Ident-Prufung — wir grenzen, wann \"anonymisiert\" noch PHI ist.",
    "Breach-Risiko-Mapping — wir zeigen, wo eine Prüfung scheitern würde.",
    "Minimum-Necessary-Review — wir prüfen, wer mehr PHI sieht als nötig.",
    "Audit-Vorbereitung — wir simulieren die HIPAA-Revision vor der echten.",
    "Vendor-PHI-Flow — wir kartieren, wo Patientendaten das Haus verlassen.",
    "Policy-Paket — wir liefern die internen Regeln, die Prüfer einfordern."],
```

**Step 2: Author the remaining 46 centers** following the identical pattern — 7+ concrete deliverables each, derived from that center's `value_prop` domain. Rule for each entry:
- Starts with a concrete deliverable NAME (Substantiv/Phrase auf Deutsch).
- Followed by " — wir ..." describing what the client RECEIVES (a check, a document, a number, a map, a dry-run).
- NEVER a question. NEVER "ein fertiges Ergebnis". NEVER restating the firm name as a service.
- Minimum 7 entries; 8 is fine.

**Step 3: Verify count**
Run:
```bash
cd /home/eri-irfos/projects/coevolution-factory/factory
python3 - <<'PY'
import catalog
short = [c["slug"] for c in catalog.CENTERS if len(c.get("products", [])) < 7]
print("centers with <7 products:", short)
assert not short, "every center needs >=7 products"
print("OK: all", len(catalog.CENTERS), "centers have >=7 products")
PY
```
Expected: `OK: all 51 centers have >=7 products`

**Step 4: Commit**
```bash
git add factory/catalog.py
git commit -m "feat(catalog): add real product/deliverable lists (>=7) per center"
```

---

## Task 2: Replace the modal sectionblock HTML

**Objective:** Remove `whatyouget` + `servicelist` blocks; add one `products` block.

**Files:**
- Modify: `factory/runtime.py:2382-2391`

**Step 1: Replace the block**
Find (exact):
```python
<div class="sectionblock">
<div class="whatyouget">
<h3>{t['what_you_get_title']}</h3>
<ul><li>{t['what_you_get_1']}</li><li>{t['what_you_get_2']}</li><li>{t['what_you_get_3']}</li></ul>
</div>
<div class="servicelist">
<h4>{t['services_title']}</h4>
<ul>{services_html}</ul>
</div>
</div>
```
Replace with:
```python
<div class="sectionblock">
<div class="productsblock">
<h3>{t['products_title']}</h3>
<ul>{products_html}</ul>
</div>
</div>
```

**Step 2: Confirm no other reference to whatyouget/servicelist/services_html remains** in the modal template (search `what_you_get_|servicelist|services_html|services_title`).

---

## Task 3: Build `products_html` in center_card_html

**Objective:** Compute the product list HTML from the new `products` field.

**Files:**
- Modify: `factory/runtime.py` (near where `services_html` was built, ~line 2162-2171)

**Step 1: Replace the old `services_html` build** (the block that reads `ucs = c.get("use_cases")` and builds `services_html`) with:
```python
    # Real product/deliverable list — concrete things this firm produces for
    # a client, from catalog.py `products`. Plain language, no prompts.
    _prods = c.get("products") or []
    products_html = (
        "".join(f'<li>{html.escape(p)}</li>' for p in _prods) if _prods else "")
```

**Step 2: Confirm `ucs` (use_cases) is no longer referenced in center_card_html** (it was only used for the deleted servicelist). If `ucs` is still defined and unused, leave it or delete — but do NOT render it.

---

## Task 4: i18n keys

**Objective:** Add `products_title`; remove dead `what_you_get_*` + `services_title` keys.

**Files:**
- Modify: `factory/runtime.py` EN dict (~line 1855) and DE dict (~line 1949)

**Step 1: Add `products_title`** to both dicts:
EN: `"products_title": "Products & Services",`
DE: `"products_title": "Produkte & Leistungen",`

**Step 2: Remove** the now-dead keys `what_you_get_title`, `what_you_get_1/2/3`, `services_title` from both dicts (they are no longer rendered). Keep `hire_button`, `buy_button`, `kpi_*` etc.

---

## Task 5: CSS for the products block

**Objective:** Style `.productsblock` (reuse the existing dark-card look).

**Files:**
- Modify: `factory/runtime.py` CSS (~line 2299, where `.servicelist` rules live)

**Step 1: Replace the `.servicelist` CSS rules** (`.servicelist`, `.servicelist h4`, `.servicelist ul`, `.servicelist li`) with:
```css
#cmbody .productsblock{{margin-top:14px;padding:16px 18px;background:#0f141d;border:1px solid #1c2733;border-radius:14px}}
#cmbody .productsblock h3{{margin:0 0 10px;font-size:11px;color:#8b98a9;text-transform:uppercase;letter-spacing:.1em;font-weight:700}}
#cmbody .productsblock ul{{margin:0;padding-left:18px;color:#c7d2e0;font-size:13px;line-height:1.7}}
#cmbody .productsblock li{{margin:0}}
```

---

## Task 6: Pre-flight (local)

**Objective:** Prove the modal renders with real products and no dead references.

**Step 1: Run**
```bash
cd /home/eri-irfos/projects/coevolution-factory/factory
python3 - <<'PY'
import sys, re; sys.path.insert(0,'.')
import runtime, catalog
for slug in ('nonprofit-gov','gdpr-guard'):
    for lang in ('en','de'):
        h = runtime.center_card_html(slug, lang)
        assert '<script>' in h
        m = re.search(r'<script>(.*?)</script>', h, re.S)
        open('/tmp/cm.js','w').write(m.group(1))
        assert 'Produkte & Leistungen' in h or 'Products & Services' in h
        assert 'class="productsblock"' in h
        # at least 7 product <li> present
        assert h.count('<li>') >= 7, f"{slug} {lang}: <7 product items"
        # dead stuff gone
        assert 'Was du bekommst' not in h and 'What you get' not in h
        assert 'servicelist' not in h
        assert 'Do we need a DPIA' not in h  # no prompt text
print("RENDER OK: real product list, dead boxes gone (en/de x 2)")
PY
node --check /tmp/cm.js && echo "PARSES OK" || echo "SYNTAX ERROR"
```
Expected: `RENDER OK: ...` and `PARSES OK`

**Step 2: Commit**
```bash
git add factory/runtime.py
git commit -m "feat(modal): replace self-evident + prompt boxes with real product list"
```

---

## Task 7: Push + deploy + live verify

**Objective:** Ship and confirm live.

**Step 1: Push**
```bash
cd /home/eri-irfos/projects/coevolution-factory
git push origin master
```

**Step 2: Deploy (retry loop for Fly flakiness)**
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

**Step 3: Live verify**
```bash
python3 - <<'PY'
import urllib.request, re
BASE="https://coevolution-factory-sparkling-mountain-1802.fly.dev"
for slug,lang in [('gdpr-guard','de'),('nonprofit-gov','de')]:
    html=urllib.request.urlopen(f"{BASE}/{slug}?lang={lang}", timeout=25).read().decode()
    print(slug, lang,
          "| products block:", 'class="productsblock"' in html,
          "| title:", 'Produkte & Leistungen' in html,
          "| <li> count:", html.count('<li>'))
PY
```
Expected: `products block: True | title: True | <li> count: >=7`

---

## Risks / tradeoffs / open questions

- **Volume:** Authoring 51×7 concrete deliverables is real content work. The plan fully specifies 5 centers and a strict rule for the rest; the implementer must author all 51 with ≥7 each (verified in Task 1 Step 3). No placeholders, no "TODO".
- **German only in examples:** Product strings in catalog.py are authored in German (matches the DE-first UI). The EN modal falls back to the same `products` field (no EN translation layer exists for it). Acceptable — the list is the same concrete deliverable in both langs; if bilingual polish is wanted later, add an EN `products` field. Flag if EN must be separately authored now.
- **`use_cases` still in catalog.py:** kept (used nowhere in modal after this change; harmless). Do not delete from catalog.py — other code may reference it.
- **KPI "Status" tile + green buy button:** untouched by this plan (already correct per prior turns).
