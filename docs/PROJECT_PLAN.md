# Projektplan (MVP)

## Ziel des MVP

Ein spielbarer vertikaler Slice:

- Spieleraktion senden
- KI erzeugt Reaktion/Narration
- Ergebnis wird als Sessionzustand gespeichert

## Phasen

1. Basis (abgeschlossen/gestartet)
- Python API Grundgeruest (FastAPI)
- Healthcheck + erster Story-Turn Endpoint
- Test-Setup mit Pytest
- Dokumentationsstruktur

2. Persistenz
- SQLAlchemy integrieren
- Modelle: User, Character, GameSession, Turn
- Migrationen mit Alembic

3. AI-Integration
- AI-Service mit Prompt-Templates
- Response-Schema validieren
- Fehlerbehandlung/Timeout/Retry
- Setup-Agent + Session-Policy Builder
- Action-Gateway (`execute` und `suggest`)
- TTLock 2-Phasenfreigabe fuer Oeffnen/Schliessen
- Bildpruefungs-Service (automatisiert)
- Integrations-Provisioning (Chaster/Emlalock Sessionanlage im Setup, falls API-seitig moeglich)

4. Gameplay-Kern
- Charakterwerte (z. B. Stärke, Intelligenz, Charisma)
- einfacher Skill-Check
- Inventar-Basis

5. Frontend-Basis
- einfacher Client fuer Login/Session/Turn-Loop

6. Erweiterungen (nach MVP)
- Domain `world` aktivieren
- Domain `combat` aktivieren

7. Betrieb/Skalierung
- Docker-Stack definieren
- horizontale Skalierung der API-Instanzen
- Monitoring + Backup-Strategie

## Definition of Done (MVP)

- End-to-end: Spieler gibt Aktion ein, erhaelt KI-Antwort, Zustand wird gespeichert
- Tests fuer Kernablauf vorhanden
- Grunddokumentation aktuell
