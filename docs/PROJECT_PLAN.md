# Projektplan (MVP)

## Ziel des MVP

Ein spielbarer vertikaler Slice:

- Spieleraktion senden
- KI erzeugt Reaktion/Narration
- Ergebnis wird als Sessionzustand gespeichert

## Priorisierung (Stand 2026-02-23)

1. Architektur-Refactoring als naechste Prioritaet
2. Containerisierung (Docker/Compose)
3. Async Jobs/Worker + Observability-Basis
4. Weitere Feature-Entwicklung (Inventar/Quests etc.)

## Phasen

0. Architektur-Refactoring (naechste Prioritaet)
- Frontend und Backend strukturell trennen (bei Monorepo-Beibehaltung)
- Modulgrenzen im Backend schaerfen (modularer Monolith)
- Routen-Dateien aufbrechen in klar getrennte Module/Use-Cases
- Tool-/Connector-Schicht mit klaren Interfaces vorbereiten
- Grundlage fuer Docker-Deploy, Worker und Observability schaffen

Meilenstein R1 (naechster testbarer Stand):
- Setup-Router ist funktional entkoppelt (Domain/Infra-Helfer in eigenen Modulen, keine breite `legacy.routes`-Kopplung).
- API/Web-Router-Split ist stabil und durchgaengig eingebunden.
- Test-Gate: `python -m pytest` gruen in der Projekt-venv + kurzer API-Smoke-Run.
- Zielkorridor: ca. 1-2 Arbeitstage ab aktuellem Stand (bei stabiler Umgebung und ohne Scope-Erweiterung).

R1-Status:
- Erreicht am 2026-02-23 (Testlauf in `.venv312`: `26 passed`).
- Naechster Schritt: Release-Preparing fuer Version `0.1.0` (Version-Bump, Changelog, Tag/Release-Notizen).

1. Basis (abgeschlossen/gestartet)
- Python API Grundgeruest (FastAPI)
- Healthcheck + erster Story-Turn Endpoint
- Test-Setup mit Pytest
- Dokumentationsstruktur

2. Persistenz
- SQLAlchemy integriert
- Modelle umgesetzt: User, Character, ChastitySession, Turn
- Migrationen mit Alembic (naechster Schritt)

3. AI-Integration
- AI-Service Interface + erster OpenAI Adapter umgesetzt
- Response-Schema validiert
- Fehlerbehandlung/Timeout/Retry (Basis)
- Setup-Agent + Session-Policy Builder umgesetzt
- Setup-Fragebogen fuer Neigungen (BDSM-test-aehnlich, consent-basiert)
- Psychogramm-Erzeugung zur Scharfstellung des KI-Charakterprofils
- Action-Gateway (`execute` und `suggest`)
- TTLock 2-Phasenfreigabe fuer Oeffnen/Schliessen
- Bildpruefungs-Service (automatisiert)
- Integrations-Provisioning (Chaster/Emlalock Sessionanlage im Setup, falls API-seitig moeglich)

4. Gameplay-Kern
- Charakterwerte (z. B. Staerke, Intelligenz, Charisma)
- einfacher Skill-Check
- Inventar-Basis

5. Frontend-Basis
- einfacher Client fuer Login/Session/Turn-Loop
- i18n-Basis fuer Deutsch/Englisch in API und UI
- Accordion-Setup-Flow mit Schritt-Sperren, Auto-Navigation und Confirm-Gate vor `Complete Setup`
- Dashboard fuer technische Prozesssicht (Setup-Status, IDs, Vertrags-/LLM-Uebersicht, letzte Events)

6. Betrieb/Skalierung
- Docker-Stack definieren
- horizontale Skalierung der API-Instanzen
- Monitoring + Backup-Strategie

## Definition of Done (MVP)

- End-to-end: Spieler gibt Aktion ein, erhaelt KI-Antwort, Turn wird persistiert
- Tests fuer Kernablauf vorhanden
- Grunddokumentation aktuell
