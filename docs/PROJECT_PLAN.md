# Projektplan (MVP)

## Ziel des MVP

Ein spielbarer vertikaler Slice:

- Spieleraktion senden
- KI erzeugt Reaktion/Narration
- Ergebnis wird als Sessionzustand gespeichert

## Phasen

1. Basis (abgeschlossen/gestartet)
- Flask API Grundgeruest
- Healthcheck + erster Story-Turn Endpoint
- Test-Setup mit Pytest
- Dokumentationsstruktur

2. Persistenz
- SQLAlchemy integrieren
- Modelle: User, Character, GameSession, WorldState, Turn
- Migrationen mit Alembic

3. AI-Integration
- AI-Service mit Prompt-Templates
- Response-Schema validieren
- Fehlerbehandlung/Timeout/Retry

4. Gameplay-Kern
- Charakterwerte (z. B. Stärke, Intelligenz, Charisma)
- einfacher Skill-Check
- Inventar-Basis

5. Frontend-Basis
- einfacher Client fuer Login/Session/Turn-Loop

## Definition of Done (MVP)

- End-to-end: Spieler gibt Aktion ein, erhaelt KI-Antwort, Zustand wird gespeichert
- Tests fuer Kernablauf vorhanden
- Grunddokumentation aktuell
