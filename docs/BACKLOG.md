# Backlog

## Prioritaet P0

- [x] Setup-/Initialisierungsprozess (Fragebogen -> Policy-Entwurf -> Bestaetigung -> aktive Session)
- [x] Psychologischer Neigungsfragebogen im Setup (BDSM-test-aehnlich, consent-basiert)
- [x] Psychogramm-Generierung aus Setup-Antworten zur KI-Profilschaerfung
- [x] Policy-Versionierung inkl. Setup-Snapshot pro Session
- [x] Datenbankanbindung mit SQLAlchemy
- [x] Session- und Charaktermodelle
- [x] Persistenter Story-Turn-Flow
- [x] AI-Service Interface + erster OpenAI Adapter

## Prioritaet P0.5 (naechster Fokus)

- [x] Architektur-Refactoring: API/Web-Routen entflechten und in Module aufteilen
- [x] Frontend/Backend-Trennung im Monorepo vorbereiten
- [x] Tool-/Connector-Abstraktion als eigene Schicht etablieren
- [ ] Docker-Compose Dev-Setup definieren (Option A zuerst)

## Refactoring-Fortschritt (Stand 2026-02-23)

- [x] API-Schemas ausgelagert (`src/chastease/api/schemas.py`)
- [x] Questionnaire/Translations ausgelagert (`src/chastease/api/questionnaire.py`)
- [x] API-Router physisch getrennt (`src/chastease/api/routers/*`)
- [x] Setup-Endpunkte in eigenen Router verschoben (`src/chastease/api/routers/setup.py`)
- [x] Web-Router in Teilrouter aufgeteilt (`src/chastease/web/routers/*`)
- [x] Setup-Router von `legacy.routes` entkoppelt (Domain-Regeln in `src/chastease/api/setup_domain.py`)
- [x] Verbleibende `legacy`-Abhaengigkeiten im Setup entfernt (`setup_infra`/`setup_ai` auf Runtime-/Service-Module umgestellt)
- [x] API-Router von `legacy.routes` entkoppelt (gemeinsame Runtime-Helfer in `src/chastease/api/runtime.py`)
- [x] Tool-Registry/Policy-Layer eingefuehrt (`src/chastease/connectors/tool_registry.py`)
- [x] LLM-Connector-Gateway eingefuehrt (`src/chastease/connectors/llm_connector.py`)
- [x] Frontend/Backend-Router-Boundaries vorbereitet (`src/chastease/frontend/`, `src/chastease/backend/`)
- [x] Laufzeitvalidierung in Zielumgebung (`pytest` + API-Smoke) als Test-Gate

## Naechster testbarer Stand (Milestone R1)

- Kriterium 1: `src/chastease/api/routers/setup.py` ohne direkte `legacy.*`-Alias-Aufrufe (ausser klar definierten Infrastruktur-Ports).
- Kriterium 2: `python -m pytest` in Projekt-venv laeuft gruen. (erreicht in `.venv312`: 27 passed)
- Kriterium 3: Smoke-Flow erfolgreich: `/api/v1/health`, Auth-Login/Register, Setup Start->Answers->Complete, `/api/v1/chat/turn`.

## Prioritaet P1

- [ ] Authentifizierung (JWT oder Session-basiert)
- [ ] Mehrsprachigkeit (Deutsch/Englisch) in API, UI und Setup-Flow
- [ ] Inventar- und Itemsystem (einfach)
- [ ] Prompt-Template Versionierung

## Prioritaet P2

- [ ] Questgenerator und Questfortschritt
- [ ] Monitoring (Sentry/OpenTelemetry)
- [ ] Szenario-Bibliothek fuer Keyholder-Interaktionsmuster
- [ ] Toy-/Geraete-Praeferenzen im Setup inkl. Policy-Ableitung
- [ ] Trigger-Kategorien und feinere Safety-Filter im Psychogramm/Policy-Layer
