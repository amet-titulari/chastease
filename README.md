# Chastease 🔒

Eine immersive, datenschutzfreundliche Web-Applikation für KI-gestützte Chastity-Sessions mit realistischer Keyholder-Persona.

## Projektübersicht

Chastease ermöglicht es Nutzenden, realistische Chastity-Sessions zu erleben, in denen eine KI die Rolle der Keyholderin übernimmt. Die Applikation läuft vollständig lokal im Browser und speichert alle Daten privat auf dem eigenen Gerät – keine Cloud, keine externen Server für persönliche Daten.

## Features (Übersicht)

- **KI-Keyholderin** – Anpassbare Persona mit konsistentem Charakter
- **Session-Mechanik** – Zufällige Sperrdauern, Timer-Management
- **Bildverifikation** – Optionale Verifikation mit nummerierten Plomben
- **Aufgaben-System** – Challenges mit Belohnungen und Bestrafungen
- **Sicherheitssystem** – Ampelsystem, Safeword, Emergency Release
- **Benachrichtigungen** – Timer, Erinnerungen, Nachrichten der Keyholderin

## Dokumentation

| Dokument | Inhalt |
|---|---|
| [VISION.md](docs/VISION.md) | Projektziel, Zielgruppe, Werte |
| [REQUIREMENTS.md](docs/REQUIREMENTS.md) | Funktionale & nicht-funktionale Anforderungen |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Tech-Stack, Systemdesign |
| [USER_STORIES.md](docs/USER_STORIES.md) | Nutzungsszenarien |
| [AI_DESIGN.md](docs/AI_DESIGN.md) | Keyholder-Persona & Prompt-Engineering |
| [ROADMAP.md](docs/ROADMAP.md) | Priorisierte Feature-Planung |

## Tech-Stack

- **Backend**: Python 3.12+ / FastAPI
- **Frontend**: Jinja2 + HTMX
- **Datenbank**: SQLite (lokal)
- **KI**: Abstraktionsschicht – Standard xAI (Grok), erweiterbar auf lokale LLMs

## Schnellstart

> Wird nach erstem Development-Sprint ergänzt.

## Lizenz

Privates Projekt – alle Rechte vorbehalten.
