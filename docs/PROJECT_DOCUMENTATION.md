# Projektdokumentation: Chastease

Dieses Dokument ist der Einstiegspunkt fuer Produkt, Architektur und Umsetzungsplanung.

## Ziel des Projekts

Chastease ist ein KI-gestuetztes Rollenspiel mit Python-API als technischem Kern.
Das System soll modular, testbar und langfristig erweiterbar sein.

## Dokumentationsstruktur

1. Produkt
- `docs/PRODUCT_VISION.md`
- `docs/REQUIREMENTS_SRS.md`
- `docs/UI_UX_REQUIREMENTS.md`
- `docs/BACKLOG.md`
- `docs/PROJECT_PLAN.md`

2. Architektur
- `docs/ARCHITECTURE.md`
- `docs/architecture/C4_SYSTEM_CONTEXT.md`
- `docs/architecture/C4_CONTAINER.md`
- `docs/architecture/C4_COMPONENT_BACKEND.md`
- `docs/architecture/ACTION_MATRIX.md`
- `docs/architecture/PSYCHOGRAM_SCHEMA.md`
- `docs/architecture/UML_DOMAIN_MODEL.md`
- `docs/architecture/UML_SEQUENCE_STORY_TURN.md`
- `docs/architecture/UML_SEQUENCE_SETUP_LIFECYCLE.md`
- `docs/architecture/UML_SEQUENCE_CHAT_ACTION_EXECUTION.md`
- `docs/architecture/UML_SEQUENCE_HYGIENE_OPEN.md`
- `docs/architecture/UML_SEQUENCE_IMAGE_VERIFICATION.md`
- `docs/architecture/UML_SEQUENCE_EMERGENCY_ABORT.md`
- `docs/architecture/UML_SEQUENCE_DEVOPS_IMAGE_BUILD.md`

3. Architekturentscheidungen (ADR)
- `docs/adr/ADR-001-modular-monolith.md`
- `docs/adr/ADR-002-api-framework.md`

## Lesereihenfolge (Empfehlung)

1. Produktvision
2. Architekturueberblick
3. C4 Kontext + Container + Komponenten
4. UML Domain + Sequenz
5. Projektplan + Backlog
6. ADRs

## Aktueller Stand (2026-02-26)

- Release-Stand: `0.2.0` (inkl. nachgelagerter Hotfixes auf `main`).
- Backend/Chat:
	- Striktes Action-Tag-Handling mit Repair-Round und robustem Parsing aktiv.
	- Notfall-Abbruch fuehrt direkte `ttlock_open`-Notfalloeffnung aus; Session/Vertrag werden erst nach erfolgreicher Oeffnung invalidiert/archiviert.
	- Bestaetigungs- und Trigger-Erkennung fuer Notfallabbruch wurde gehaertet (`rot/red`, `abbrechen`, `stop/stopp`, etc.).
	- Oeffnungslimits werden serverseitig erzwungen (`opening_limit_period` + `max_openings_in_period`) mit laufender Ereignis-Historie.
- Frontend/UI:
	- Dashboard-Polling deutlich reduziert (Cache + Dedupe + Sichtbarkeitslogik).
	- Image-Verification-Action-Card auf One-Button-Flow umgestellt (`Bild aufnehmen` -> Vorschau -> `Bild prüfen`), ohne JSON-Rohpayload.
	- Sichtbarer Status waehrend Bildpruefung integriert.
- Setup/Session:
	- Setup-/Session-Sync fuer Integrationen und Consent stabilisiert.
	- Session-/Contract-Status nach Notfallabbruch konsistent auf Neustart-Pfad ausgelegt.
- DevOps:
	- Docker-Compose Dev-Setup (Option A) umgesetzt.
	- Manueller GHCR-Image-Build via GitHub Action verfuegbar.

## Naechste sinnvolle Schritte

- Regressionstests fuer Notfallabbruch + Oeffnungslimit-Pfade erweitern (inkl. `ttlock_open`-Fail/Retry-Szenarien).
- Optionales observability-Logging fuer entfernte/unterdrueckte Machine-Tags und Notfallpfad-Transitions.
- Release-Nachzug mit Tagging (z. B. `v0.2.0`) falls noch nicht gesetzt.
