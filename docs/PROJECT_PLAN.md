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
- Charakterwerte (z. B. Stärke, Intelligenz, Charisma)
- einfacher Skill-Check
- Inventar-Basis

5. Frontend-Basis
- einfacher Client fuer Login/Session/Turn-Loop
- i18n-Basis fuer Deutsch/Englisch in API und UI

6. Betrieb/Skalierung
- Docker-Stack definieren
- horizontale Skalierung der API-Instanzen
- Monitoring + Backup-Strategie

## Definition of Done (MVP)

- End-to-end: Spieler gibt Aktion ein, erhaelt KI-Antwort, Turn wird persistiert
- Tests fuer Kernablauf vorhanden
- Grunddokumentation aktuell
