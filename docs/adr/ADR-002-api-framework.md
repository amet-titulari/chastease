# ADR-002: API Framework Wahl (FastAPI vs Flask)

- Status: Accepted
- Datum: 2026-02-21

## Kontext

Das Projekt benoetigt:
- stark typisierte API-Vertraege
- gute OpenAPI-Unterstuetzung
- saubere Async-Integration fuer externe APIs/Agentenpfade
- hohe Entwicklungsgeschwindigkeit bei wachsendem Integrationsumfang

## Entscheidung

Die Zielarchitektur verwendet FastAPI als bevorzugtes API-Framework.

## Begruendung

- Native OpenAPI/Swagger-Generierung
- Typisierung via Pydantic erleichtert Request/Response-Vertraege
- Async-Pfade fuer Integrations- und KI-nahe Operationen besser abbildbar
- Gute Passung fuer API-first Entwicklung und spaetere Client-Generierung

## Konsequenzen

Positiv:
- Schnellere, robustere API-Vertragsentwicklung
- Besseres Fundament fuer skalierbare Integrationspfade

Negativ:
- Anfangsaufwand fuer App-Factory/Router-Struktur

## Umsetzungsleitlinie

- FastAPI als verbindliche Basis fuer neue API-Endpunkte verwenden.
