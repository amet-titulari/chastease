# Architekturueberblick

## Systemkontext

- Client (Web/SPA) spricht mit Flask-API
- Flask-API kapselt Game-Logik und Persistenz
- AI-Adapter kapselt LLM-Aufrufe
- Datenbank speichert Spieler-, Charakter- und Weltzustand

## Startstruktur (Modular Monolith)

`src/chastease/`:

- `api/` - HTTP-Endpunkte
- `config.py` - Laufzeitkonfiguration
- spaeter:
- `domains/characters/`
- `domains/world/`
- `domains/quests/`
- `domains/combat/`
- `services/ai/`
- `repositories/`

## Architekturprinzipien

- App-Factory Pattern fuer testbare Flask-Instanzen
- Domänenlogik getrennt von API-Transportschicht
- AI-Aufrufe nur ueber dedizierten Service
- Jede Spieleraktion als Event dokumentierbar (Audit/Replay)

## API Versionierung

- Prefix: `/api/v1`
- Breaking changes in neue Version (`/api/v2`)

## Nicht-funktionale Ziele

- Testbarkeit: Unit- und API-Tests ab MVP
- Erweiterbarkeit: klare Modulgrenzen
- Beobachtbarkeit: Logging und spaeter Tracing/Metriken
