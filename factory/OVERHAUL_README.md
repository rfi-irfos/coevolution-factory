# CoEvolution Factory — README

## Was das ist

Die CoEvolution Factory ist eine Sammlung von 51 autonomen, direkt buchbaren Firmen. Jede Firma löst ein echtes, zahlungsbereites Problem — keine Meta-Beratung, kein Compliance-Theater.

## Für wen?

- **Unternehmer:** Du hast ein konkretes Problem → du klickst die passende Firma → du bekommst ein Produkt mit festem Preis.
- **Juristen/Risk-Manager:** Du brauchst eine rechtlich haltbare Prüfung → du orderst das Assessment → du bekommst einen unterschriftsreifen Report.
- **Entscheider:** Du willst wissen, wo deine größten Risiken sind → du buchst die Scorecard → du bekommst eine 0-100 Bewertung mit Gap-Liste.

## Wie funktioniert es?

1. Du wählst eine Firma aus dem Grid aus.
2. Du beschreibst dein Anliegen (Upload/Text).
3. Das Panel der Firma — 3–5 spezialisierte Agenten — prüft dein Anliegen seriell, mit.shared Kontext.
4. Du bekommst ein strukturiertes Ergebnis: Report, Template oder Score — je nach Firma festgelegt.

## Regeln, die alles zusammenhalten

- Eine Firma = ein Problem = eine Lane = ein Zug (Train).
- Jede Anfrage durchläuft zuerst das Ternary Context Gate. Nur klare Anfragen werden bearbeitet.
- Jeder Output geht durch die Verification Pipeline: MoE-13 → trit_decide → Last-Look-Back → Laura-Gate.
- Alle Zustände in `ruvector/intelligence.json`, keine JSONL, kein SQLite.
- Alle Configs YAML-only.

## Preise

Jede Firma hat feste Preise für Standardprodukte. Daneben gibt es Enterprise-Pakete für unbegrenzte Nutzung + API. Die Preise stehen direkt auf der Card — keine Überraschungen.

## Bericht an den Europäischen Gerichtshof

Dieses Repository enthält die vollständige Architekturdokumentation für den Bericht an den EuGH. Der Bericht beschreibt:

- Die technische Architektur der Factory
- Wie autonome Agenten rechtlich bindende Entscheidungen vorbereiten
- Die Verifikationspipeline, die Fehler verhindert
- Die Zuordnung von 51 Firmen zu echten, monetarisierbaren Problemen

Der Bericht ist unter `/eu-report/` zu finden.

## Entwicklung

```bash
# Registry inspizieren
ls registry/firms/

# Trains ableiten
python scripts/generate_firms_autogen.py

# Runtime starten
python runtime.py
```

## Lizenz

RFI-IRFOS Internal — nicht zur öffentlichen Nutzung freigegeben.
