# Architekturueberblick

Dieses Dokument beschreibt die Leitplanken fuer die technische Umsetzung.  
Detaildiagramme liegen unter `/Users/swisi/Repos/privat/chastease/docs/architecture/`.

## Architekturziele

*   Modulare Erweiterbarkeit ohne fruehen Microservice-Overhead
*   Robuste Trennung von API, Domäne, Persistenz und KI-Integration
*   Nachvollziehbarer Story-Verlauf pro Session (Replay-faehig)
*   Solide Testbarkeit auf Unit- und API-Ebene

## Architekturansatz

*   Stil: Modular Monolith
*   Backend: Python API, FastAPI bevorzugt fuer Zielarchitektur
*   Aktueller Code-Stand: FastAPI-Scaffold
*   Persistenz: PostgreSQL (spaeter mit SQLAlchemy + Alembic)
*   KI: gekapselter AI-Service-Adapter
*   API-Versionierung: `/api/v1`
*   Deploymentziel: Docker-Stack mit horizontaler Skalierung

## Modulgrenzen (Zielstruktur)

`/Users/swisi/Repos/privat/chastease/src/chastease/`

*   `api/`
*   `domains/characters/`
*   `domains/quests/`
*   `domains/sessions/`
*   `services/ai/`
*   `repositories/`
*   `shared/`

## Layering-Regeln

*   API Layer darf Domain Use Cases aufrufen, aber keine SQL-Details enthalten.
*   Domain Layer ist framework-arm und enthaelt Spielregeln.
*   Repository Layer kapselt Datenzugriff und Transaktionen.
*   AI-Service darf nur ueber klar definiertes Interface aus Use Cases aufgerufen werden.

## Qualitaetsanforderungen

*   Testbarkeit:
    *   Unit-Tests fuer Domainregeln
    *   API-Tests fuer Endpunkte
*   Zuverlaessigkeit:
    *   Timeouts und Retries bei KI-Aufrufen
    *   Sauberer Fehlerkanal mit stabilen Fehlercodes
*   Performance:
    *   Chat-Latenz hat Prioritaet gegenueber Aktionspfad-Latenz
    *   Agenten-/Integrationsaktionen duerfen langsamer sein als Chatantworten
*   Wartbarkeit:
    *   ADRs fuer zentrale Architekturentscheidungen
    *   Konsistente Modulnamensgebung und Grenzdisziplin

## Auth-Strategie (Vorschlag)

*   MVP:
    *   Benutzername/Passwort als Mindestanforderung
    *   serverseitig in-memory gehaltene Auth-Tokens (aktuelle Implementierung)
*   Zielausbau:
    *   JWT Access/Refresh fuer API-Sessions
    *   Passkey (WebAuthn) als bevorzugter Login
    *   OAuth als optionale Erweiterung

## Referenzen

*   C4 System Context:
    *   `/Users/swisi/Repos/privat/chastease/docs/architecture/C4_SYSTEM_CONTEXT.md`
*   C4 Container:
    *   `/Users/swisi/Repos/privat/chastease/docs/architecture/C4_CONTAINER.md`
*   C4 Komponenten (Backend):
    *   `/Users/swisi/Repos/privat/chastease/docs/architecture/C4_COMPONENT_BACKEND.md`
*   Action Matrix:
    *   `/Users/swisi/Repos/privat/chastease/docs/architecture/ACTION_MATRIX.md`
*   Psychogramm Schema:
    *   `/Users/swisi/Repos/privat/chastease/docs/architecture/PSYCHOGRAM_SCHEMA.md`
*   UML Domain Model:
    *   `/Users/swisi/Repos/privat/chastease/docs/architecture/UML_DOMAIN_MODEL.md`
*   UML Story Turn Sequence:
    *   `/Users/swisi/Repos/privat/chastease/docs/architecture/UML_SEQUENCE_STORY_TURN.md`
*   UML Setup Lifecycle Sequence:
    *   `/Users/swisi/Repos/privat/chastease/docs/architecture/UML_SEQUENCE_SETUP_LIFECYCLE.md`
*   ADR API Framework:
    *   `/Users/swisi/Repos/privat/chastease/docs/adr/ADR-002-api-framework.md`
