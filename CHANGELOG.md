# Changelog

## 0.0.3 - 2026-02-21

- Setup-Prototyp funktional ausgebaut (Start, Fragebogen, Preview, Abschluss).
- BDSM-test-inspirierter Fragebogen mit Psychogramm-Ableitung integriert.
- Mehrsprachigkeit im Prototyp erweitert (`de`/`en`) fuer Setup und Story-Turn.
- Fragebogenskala auf `1-10` umgestellt, inklusive Slider-UI in der Demo.
- Datei-basierte Persistenz fuer Setup-Sessions (`data/setup_sessions.json`) eingefuehrt.
- Tests fuer Setup-Flow, i18n und Demo erweitert.

## 0.0.2 - 2026-02-21

- Produkt-, Architektur- und SRS-Dokumente konsolidiert und sprachlich/fachlich geschärft.
- Domains `world` und `combat` vollständig aus allen Dokumenten entfernt.
- `GameSession` konsistent auf `ChastitySession` umgestellt.
- Setup/Initialisierung in Priorität P0 aufgenommen.
- Psychologischer Setup-Fragebogen und Psychogramm-Konzept ergänzt.
- Neues Architekturartefakt: `docs/architecture/PSYCHOGRAM_SCHEMA.md`.

## 0.0.1 - 2026-02-21

- Initiale Projektgrundlage mit API, Tests und Dokumentationsstruktur.
- Architektur- und Anforderungsdokumentation mit C4, UML, Action-Matrix und ADRs.
- Migration des API-Scaffolds von Flask auf FastAPI.
- UI/UX-Anforderungsschicht fuer responsive, geraeteuebergreifende Nutzung.
