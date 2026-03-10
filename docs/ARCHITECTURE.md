# Architektur – Chastease

## Überblick

Chastease folgt einem **privaten Client-Server-Modell**: Das Python-Backend läuft auf einem dedizierten Heimgerät (PC, Heimserver oder NAS). Alle Daten – Sessionverläufe, Chats, Fotos, Konfiguration – werden **ausschliesslich auf diesem Backend-Server** gespeichert.

Client-Geräte (Smartphone, Tablet, weiterer PC) sind **zustandsarme Browser-Clients**: Die Anwendung persistiert dort absichtlich keine langlebigen App-Daten. Fotos (z.B. Verifikationsaufnahmen) werden direkt via Upload-Stream an das Backend übertragen und sollen nicht in der Bildergalerie des Clients landen. Unvermeidbare temporäre Zwischenspeicher des Browsers oder Betriebssystems werden minimiert, aber nicht als technisch unmöglich behauptet. Die einzige externe Verbindung sind API-Calls an den konfigurierten KI-Anbieter.

> **Deployment-Modell**: Der Backend-Server läuft im Heimnetz und ist über dessen lokale IP oder einen lokalen Hostnamen erreichbar. Ein Zugriff von ausserhalb (unterwegs) ist über ein VPN (z.B. WireGuard, Tailscale) möglich, ohne den Server direkt dem Internet auszusetzen.

```
┌─────────────────────────────────────────────────────┐
│         Browser-Client (Phone / Tablet / PC)        │
│         !! kein lokaler Datenspeicher !!            │
│  ┌─────────────────────────────────────────────┐   │
│  │  Jinja2 Templates + Vanilla JS (Fetch)      │   │
│  │  - Session Dashboard                        │   │
│  │  - Chat Interface                           │   │
│  │  - Safety Controls (persistent)             │   │
│  │  - Konfiguration                            │   │
│  │  - Foto-Upload → direkt ans Backend         │   │
│  └──────────────────┬──────────────────────────┘   │
└─────────────────────┼───────────────────────────────┘
                      │ HTTP / WebSocket (Heimnetz oder VPN)
┌─────────────────────▼───────────────────────────────┐
│         FastAPI Backend (Heimserver / NAS / PC)     │
│              !! alle Daten leben hier !!            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │  Session    │  │  Timer      │  │  Task       │ │
│  │  Service    │  │  Service    │  │  Service    │ │
│  └─────────────┘  └─────────────┘  └─────────────┘ │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │  Safety     │  │  Media      │  │  AI         │ │
│  │  Service    │  │  Service    │  │  Gateway    │ │
│  └─────────────┘  └─────────────┘  └──────┬──────┘ │
│  ┌──────────────────────────────────────┐  │       │
│  │           SQLite (lokal)             │  │       │
│  └──────────────────────────────────────┘  │       │
└────────────────────────────────────────────┼────────┘
                                             │ HTTPS
                                   ┌─────────▼─────────┐
                                   │   KI-API          │
                                   │  (Grok / OpenAI-  │
                                   │   kompatibel /    │
                                   │   lokales LLM)    │
                                   └───────────────────┘
```

---

## Tech-Stack

### Backend
| Komponente | Technologie | Begründung |
|---|---|---|
| Sprache | Python 3.12+ | Bekannt, grosse Ökosystem |
| Framework | FastAPI | Bekannt, async-fähig, automatische API-Docs |
| ORM | SQLAlchemy 2.x | Pythonische Datenbankabstraktion |
| Datenbank | SQLite | Lokal, keine Installation nötig |
| Migrationen | Alembic | Saubere DB-Schema-Verwaltung |
| Scheduling | APScheduler | Timer-Events, Erinnerungen im Hintergrund |
| WebSockets | FastAPI WebSocket | Echtzeit-Kommunikation für Chat & Timer |

### Frontend
| Komponente | Technologie | Begründung |
|---|---|---|
| Templates | Jinja2 | Vertraut, server-side rendering |
| Interaktivität | Vanilla JavaScript + Fetch API | Schneller Start fuer Testkonsole ohne Frontend-Buildschritt |
| Styling | Handgeschriebenes CSS | Leichtgewichtig fuer Alpha-Prototyp |

### KI-Integration
| Komponente | Technologie |
|---|---|
| Primär (Test) | xAI Grok API |
| Abstraktion | Eigene `AIGateway`-Klasse mit einheitlichem Interface |
| Kompatibilität | OpenAI-SDK (da Grok OpenAI-kompatibel ist) |
| Erweiterung | Lokale LLMs via `llama.cpp` HTTP-Server oder `ollama` |

---

## Datenbankschema (Übersicht)

```
personas
├── id, name, description
├── system_prompt, communication_style
└── strictness_level, created_at

sessions
├── id, persona_id (FK), player_profile_id (FK)
├── status (active / paused / completed / emergency_stopped)
├── lock_start, lock_end (geplant), lock_end_actual
├── timer_frozen (bool), freeze_start
├── min_duration_seconds, max_duration_seconds  # Intervalle als Integer-Sekunden (None = kein Maximum)
└── created_at, updated_at

player_profiles
├── id, nickname, experience_level
├── preferences_json, soft_limits_json, hard_limits_json
├── reaction_patterns_json, needs_json
└── created_at, updated_at

messages
├── id, session_id (FK)
├── role (user / assistant / system)
├── content, created_at
└── message_type (chat / event / notification)

tasks
├── id, session_id (FK)
├── title, description, deadline
├── status (pending / completed / failed / cancelled)
├── consequence_type, consequence_value
└── created_at, completed_at

verifications
├── id, session_id (FK)
├── image_path (lokal)
├── requested_seal_number, observed_seal_number
├── status (pending / confirmed / suspicious)
├── ai_response
└── requested_at

hygiene_openings
├── id, session_id (FK)
├── requested_at, approved_at, opened_at
├── due_back_at, relocked_at
├── status (requested / approved / active / overdue / closed / denied)
├── old_seal_number, new_seal_number
├── overrun_seconds
├── penalty_seconds
└── penalty_applied_at

seal_history
├── id, session_id (FK), hygiene_opening_id (FK, optional)
├── seal_number
├── status (active / destroyed / replaced)
├── applied_at, invalidated_at
└── note

safety_logs
├── id, session_id (FK)
├── event_type (safeword / yellow / red / emergency_release)
├── reason (bei emergency_release)
└── created_at

contracts
├── id, session_id (FK, unique)
├── content_text            # vollständiger Vertragstext (von KI generiert)
├── signed_at               # Zeitstempel der Unterzeichnung (NULL = noch nicht unterzeichnet)
├── parameters_snapshot     # JSON-Abbild aller Session-Parameter zum Unterzeichnungszeitpunkt
└── created_at

contract_addenda
├── id, contract_id (FK)
├── proposed_changes_json   # strukturierte Parameteränderungen
├── change_description      # was geändert wurde
├── proposed_by             # 'ai'
├── player_consent          # approved / rejected
├── player_consent_at       # Zeitstempel der Zustimmung durch den Nutzer
└── created_at

seal_history
├── id, session_id (FK), hygiene_opening_id (FK, optional)
├── seal_number
├── status (active / destroyed)
├── applied_at, invalidated_at
└── note
```

---

## Projektstruktur

```
chastease/                       # läuft auf dem Heimserver
├── README.md
├── docs/
│   ├── VISION.md
│   ├── REQUIREMENTS.md
│   ├── ARCHITECTURE.md
│   ├── USER_STORIES.md
│   ├── AI_DESIGN.md
│   └── ROADMAP.md
├── app/
│   ├── main.py                  # FastAPI App-Instanz + Startup Migration
│   ├── config.py                # Settings (Pydantic BaseSettings)
│   ├── database.py              # SQLAlchemy Engine & Session
│   ├── models/                  # SQLAlchemy ORM-Modelle
│   │   ├── session.py
│   │   ├── persona.py
│   │   ├── player_profile.py
│   │   ├── contract.py
│   │   ├── hygiene_opening.py
│   │   ├── safety_log.py
│   │   ├── verification.py
│   │   └── seal_history.py
│   ├── routers/                 # FastAPI Router
│   │   ├── health.py
│   │   ├── sessions.py
│   │   ├── hygiene.py
│   │   ├── safety.py
│   │   ├── verification.py
│   │   └── web.py
│   ├── services/                # Business Logic
│   │   ├── session_service.py
│   │   ├── timer_service.py
│   │   ├── contract_service.py
│   │   ├── hygiene_service.py
│   │   └── ai_gateway.py        # KI-Stub / Abstraktionsbasis
│   ├── templates/               # Jinja2 HTML-Templates
│   │   ├── base.html
│   │   └── dashboard.html
│   └── static/
│       ├── css/style.css
│       └── js/dashboard.js
├── data/                        # SQLite DB & lokale Mediendateien (gitignored)
│   ├── chastease.db
│   └── media/
├── alembic/                     # DB-Migrationen
├── tests/
├── requirements.txt
└── .env.example
```

---

## Sicherheitskonzept

### API-Key-Speicherung
- API-Keys werden mit `cryptography.fernet` symmetrisch verschlüsselt
- Der Schlüssel wird beim ersten Start generiert und lokal gespeichert
- Kein Klartext-Key in der Datenbank oder `.env`-Datei

### Mediendateien (Verifikationsfotos)
- Fotos werden per **Multipart-Upload direkt an das Backend gestreamt** – kein Zwischenspeichern auf dem Client-Gerät
- Das Frontend verwendet `<input type="file" capture="environment">`; die Anwendung speichert Bilder nicht absichtlich lokal oder in einer Galerie
- Server speichert Fotos ausschliesslich im `data/media/`-Verzeichnis des Backend-Servers
- Dateinamen sind nicht erratbar (UUID-basiert)
- Das `data/`-Verzeichnis ist in `.gitignore` eingetragen
- Fotos werden nicht als Inline-Bild an den Client zurückgeliefert; nur eine Bestätigung und das KI-Analyse-Ergebnis werden zurückgegeben

### Sessions-Integrität
- Safety-Endpoints sind gesondert und haben höchste Priorität
- Emergency Release schreibt immer ins Safety-Log, auch bei Fehlern

### Migrationen
- Schema wird über Alembic verwaltet (`0001`-`0003`)
- Startup führt `alembic upgrade head` aus, um DB auf aktuellen Stand zu bringen
- Für Alt-Datenbanken ohne Alembic-Versionstabelle wird baseline-Stamping durchgeführt

---

## KI-Gateway Abstraktion

```python
# Aktueller Stand: synchroner Stub fuer Vertragsgenerierung,
# erweiterbar auf async Provider (Grok/OpenAI/Ollama) in naechster Phase.
class AIGateway:
    def generate_contract(
        self,
        persona_name: str,
        player_nickname: str,
        min_duration_seconds: int,
        max_duration_seconds: int | None,
    ) -> str: ...

class GrokGateway(AIGateway): ...
class OllamaGateway(AIGateway): ...
class OpenAIGateway(AIGateway): ...
```

---

## Kommunikationsfluss (WebSocket)

```
Client                    FastAPI Backend              APScheduler
  │                            │                           │
  │── WS Connect ─────────────>│                           │
  │                            │<── Timer tick ────────────│
  │<── timer_update ───────────│                           │
  │<── keyholder_message ──────│                           │
  │── user_message ───────────>│                           │
  │                            │── AI API call ──────────> │
  │<── keyholder_response ─────│                           │
  │<── task_assigned ──────────│                           │
```
