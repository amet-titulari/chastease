# Projektplan

## Aktuelle Ausrichtung

Die naechste Entwicklungsphase ist kein reines MVP-Hardening mehr, sondern die Vorbereitung einer roleplay-zentrierten Zielarchitektur.
Der Schwerpunkt verschiebt sich von allgemeiner Chat-Funktionalitaet hin zu einem klaren RP-System mit Character Layer, Scenario Layer, Memory und zentralem Prompt-Assembly.

## Zielbild der naechsten Phase

- Chastease als spezialisierte Roleplay-App statt generischer KI-Chat mit Domänenanhang
- klare fachliche Schnitte zwischen Consent, Runtime, Roleplay und Model Gateway
- Authoring-Basis fuer Charaktere, Szenarien und Prompt-Presets
- Vorbereitung fuer langlaufende Sessions mit Summary und Memory

## Ziel des MVP

Ein spielbarer vertikaler Slice:

- Spieleraktion senden
- KI erzeugt Reaktion/Narration
- Ergebnis wird als Sessionzustand gespeichert

## Priorisierung (Stand 2026-03-07)

1. Roleplay-Architektur-Refactoring als naechste Prioritaet
2. Character-/Scenario-/Memory-Layer vorbereiten
3. Prompt-Assembly und LLM-Kontext modularisieren
4. Danach Betriebsthemen, Worker und weitere Gameplay-Features

## Phasen

0. Roleplay-Refactoring vorbereiten (naechste Prioritaet)
- Roleplay-Zielarchitektur dokumentieren
- Character, Scenario, Persona und Memory als eigene Fachbegriffe verankern
- bestehende Narration-Logik in vorbereitende Bausteine zerlegen
- Prompt-Assembly von Session-/Policy-/Runtime-Logik abgrenzen
- Grundlage fuer spaetere UI- und Authoring-Erweiterungen schaffen

Meilenstein R2 (naechster testbarer Stand):
- Ein dedizierter Roleplay-Context-Builder ist aus der bestehenden Narration extrahiert.
- Prompt-Bausteine fuer History, Policy, Live-Snapshot und Persona sind technisch getrennt.
- Zielstruktur fuer Character-Card-, Scenario- und Summary-Modelle ist dokumentiert.
- Test-Gate: bestehende Tests bleiben gruen; neue reine Unit-Tests fuer Kontextaufbereitung sind vorhanden.

Meilenstein R3:
- Character-Card-Schema und Scenario-Schema existieren.
- Persona ist fachlich vom Psychogramm getrennt.
- Session-Summary-Konzept ist implementierbar vorbereitet.

Meilenstein R1 (naechster testbarer Stand):
- Setup-Router ist funktional entkoppelt (Domain/Infra-Helfer in eigenen Modulen, keine breite `legacy.routes`-Kopplung).
- API/Web-Router-Split ist stabil und durchgaengig eingebunden.
- Test-Gate: `python -m pytest` gruen in der Projekt-venv + kurzer API-Smoke-Run.
- Zielkorridor: ca. 1-2 Arbeitstage ab aktuellem Stand (bei stabiler Umgebung und ohne Scope-Erweiterung).

R1-Status:
- Erreicht am 2026-02-23; validiert am 2026-02-25 (Testlauf in `.venv312`: `53 passed`).
- Docker-Compose Dev-Setup (Option A) ist umgesetzt; naechster Schritt ist der Alembic-Migrationspfad.

P0.5-Status (ohne Docker):
- Architektur-Refactoring abgeschlossen (API/Web-Router entkoppelt, gemeinsame Runtime-Helfer extrahiert).
- Frontend/Backend-Trennung im Monorepo vorbereitet (`src/chastease/frontend`, `src/chastease/backend`).
- Tool-/Connector-Schicht eingefuehrt (`src/chastease/connectors/tool_registry.py`, `src/chastease/connectors/llm_connector.py`).

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

4. Roleplay-Kern
- Character Persona
- Szenario-Bibliothek
- Lorebook / World Info
- Session Summary und Memory

5. Gameplay-Kern
- Charakterwerte (z. B. Staerke, Intelligenz, Charisma)
- einfacher Skill-Check
- Inventar-Basis

6. Frontend-Basis
- einfacher Client fuer Login/Session/Turn-Loop
- i18n-Basis fuer Deutsch/Englisch in API und UI
- Accordion-Setup-Flow mit Schritt-Sperren, Auto-Navigation und Confirm-Gate vor `Complete Setup`
- Dashboard fuer technische Prozesssicht (Setup-Status, IDs, Vertrags-/LLM-Uebersicht, letzte Events)
- Character-/Scenario-Auswahl und RP-Preset-UI (naechste Ausbaustufe)

7. Betrieb/Skalierung
- Docker-Stack definieren
- horizontale Skalierung der API-Instanzen
- Monitoring + Backup-Strategie

## Definition of Done (MVP)

- End-to-end: Spieler gibt Aktion ein, erhaelt KI-Antwort, Turn wird persistiert
- Tests fuer Kernablauf vorhanden
- Grunddokumentation aktuell
