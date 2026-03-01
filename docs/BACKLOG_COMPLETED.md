# Abgeschlossene Backlog Items

Archiv aller erledigten Aufgaben, organisiert chronologisch nach Abschluss.

## Prioritaet 0 (abgeschlossen)

- [x] Setup-/Initialisierungsprozess (Fragebogen -> Policy-Entwurf -> Bestaetigung -> aktive Session)
- [x] Psychologischer Neigungsfragebogen im Setup (BDSM-test-aehnlich, consent-basiert)
- [x] Psychogramm-Generierung aus Setup-Antworten zur KI-Profilschaerfung
- [x] Policy-Versionierung inkl. Setup-Snapshot pro Session
- [x] Datenbankanbindung mit SQLAlchemy
- [x] Session- und Charaktermodelle
- [x] Persistenter Story-Turn-Flow
- [x] AI-Service Interface + erster OpenAI Adapter

## Prioritaet 0 (abgeschlossen, Refactoring)

- [x] Architektur-Refactoring: API/Web-Routen entflechten und in Module aufteilen
- [x] Frontend/Backend-Trennung im Monorepo vorbereiten
- [x] Tool-/Connector-Abstraktion als eigene Schicht etablieren
- [x] Docker-Compose Dev-Setup definieren (Option A zuerst)

## Refactoring-Fortschritt (Stand 2026-02-25)

- [x] API-Schemas ausgelagert (`src/chastease/api/schemas.py`)
- [x] Questionnaire/Translations ausgelagert (`src/chastease/api/questionnaire.py`)
- [x] API-Router physisch getrennt (`src/chastease/api/routers/*`)
- [x] Setup-Endpunkte in eigenen Router verschoben (`src/chastease/api/routers/setup.py`)
- [x] Web-Router in Teilrouter aufgeteilt (`src/chastease/web/routers/*`)
- [x] Setup-Router von `legacy.routes` entkoppelt (Domain-Regeln in `src/chastease/api/setup_domain.py`)
- [x] Verbleibende `legacy`\-Abhaengigkeiten im Setup entfernt (`setup_infra`/`setup_ai` auf Runtime-/Service-Module umgestellt)
- [x] API-Router von `legacy.routes` entkoppelt (gemeinsame Runtime-Helfer in `src/chastease/api/runtime.py`)
- [x] Tool-Registry/Policy-Layer eingefuehrt (`src/chastease/connectors/tool_registry.py`)
- [x] LLM-Connector-Gateway eingefuehrt (`src/chastease/connectors/llm_connector.py`)
- [x] Frontend/Backend-Router-Boundaries vorbereitet (`src/chastease/frontend/`, `src/chastease/backend/`)
- [x] Laufzeitvalidierung in Zielumgebung (`pytest` + API-Smoke) als Test-Gate

## Naechster testbarer Stand (Milestone R1, abgeschlossen)

- [x] Kriterium 1: `src/chastease/api/routers/setup.py` ohne direkte `legacy.*`-Alias-Aufrufe (ausser klar definierten Infrastruktur-Ports).
- [x] Kriterium 2: `python -m pytest` in Projekt-venv laeuft gruen. (zuletzt: 74 passed, 1 failed; Testfall an neue Notfall-Semantik anpassen)
- [x] Kriterium 3: Smoke-Flow erfolgreich: `/api/v1/health`, Auth-Login/Register, Setup Start->Answers->Complete, `/api/v1/chat/turn`.

## Prioritaet 0 (abgeschlossen, 2026-02-26)

- [x] Regressionstests fuer Notfallabbruch + `ttlock_open`-Sonderpfad erweitern
- [x] Regressionstests fuer Oeffnungslimit (`opening_limit_period`, `max_openings_in_period`) erweitern
- [x] Optionales Observability-Logging fuer gefilterte Machine-Tags und Abbruch-Transitions (Audit-Log + Admin-View)

## Prioritaet 0 (abgeschlossen, 2026-03-01)

- [x] GitHub Release-Tagging fuer `v0.2.0` nachziehen
- [x] Die AI soll in der Lage sein die Session Informationen zu erhalten
- [x] Die AI soll die Sigelnummern aus der Session abrufen und prüfen können (initial_seal_number im Setup, runtime_seal in aktiver Session, AI kann Nummern validieren)

---

**Hinweis**: Neue abgeschlossene Items sollten regelmäßig hierher verschoben werden, um das aktive Backlog übersichtlich zu halten.
