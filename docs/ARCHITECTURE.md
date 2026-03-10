# Architektur – Chastease

## Überblick

Chastease folgt einem **privaten Client-Server-Modell**: Das Python-Backend läuft auf einem dedizierten Heimgerät (PC, Heimserver oder NAS). Alle Daten – Sessionverläufe, Chats, Fotos, Konfiguration – werden **ausschliesslich auf diesem Backend-Server** gespeichert.

Client-Geräte (Smartphone, Tablet, weiterer PC) sind **zustandslose Browser-Clients**: Sie speichern keinerlei Daten lokal. Fotos (z.B. Verifikationsaufnahmen) werden direkt via Upload-Stream an das Backend übertragen und nie im Gerätespeicher des Clients abgelegt. Die einzige externe Verbindung sind API-Calls an den konfigurierten KI-Anbieter.

> **Deployment-Modell**: Der Backend-Server läuft im Heimnetz und ist über dessen lokale IP oder einen lokalen Hostnamen erreichbar. Ein Zugriff von ausserhalb (unterwegs) ist über ein VPN (z.B. WireGuard, Tailscale) möglich, ohne den Server direkt dem Internet auszusetzen.

```
┌─────────────────────────────────────────────────────┐
│         Browser-Client (Phone / Tablet / PC)        │
│         !! kein lokaler Datenspeicher !!            │
│  ┌─────────────────────────────────────────────┐   │
│  │  Jinja2 Templates + HTMX + Alpine.js        │   │
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
| Interaktivität | HTMX | Dynamische UI ohne komplettes JS-Framework |
| Kleine Reaktivität | Alpine.js | Lokaler UI-State (z.B. Modal-Toggle) |
| Styling | Tailwind CSS | Utility-first, schnell, kein Custom-CSS nötig |

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
├── id, persona_id (FK)
├── status (active / paused / completed / emergency_stopped)
├── lock_start, lock_end (geplant), lock_end_actual
├── timer_frozen (bool), freeze_start
├── min_duration_seconds, max_duration_seconds  # Intervalle als Integer-Sekunden (None = kein Maximum)
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
├── image_path (lokal), seal_number (optional)
├── status (pending / confirmed / suspicious)
├── ai_response, created_at
└── requested_at

session_events
├── id, session_id (FK)
├── event_type (time_added / time_removed / freeze / unfreeze / reward / punishment)
├── value, reason
└── created_at

ai_config
├── id, provider (grok / openai / ollama / custom)
├── api_endpoint, model_name
└── api_key_encrypted

safety_log
├── id, session_id (FK)
├── event_type (safeword / yellow / red / emergency_release)
├── reason (bei emergency_release), created_at

contracts
├── id, session_id (FK, unique)
├── content_text            # vollständiger Vertragstext (von KI generiert)
├── signed_at               # Zeitstempel der Unterzeichnung (NULL = noch nicht unterzeichnet)
├── parameters_snapshot     # JSON-Abbild aller Session-Parameter zum Unterzeichnungszeitpunkt
└── created_at

contract_addenda
├── id, contract_id (FK)
├── change_description      # was geändert wurde
├── proposed_by             # 'ai'
├── player_consent_at       # Zeitstempel der Zustimmung durch den Nutzer
└── created_at
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
│   ├── main.py                  # FastAPI App-Instanz
│   ├── config.py                # Settings (Pydantic BaseSettings)
│   ├── database.py              # SQLAlchemy Engine & Session
│   ├── models/                  # SQLAlchemy ORM-Modelle
│   │   ├── session.py
│   │   ├── persona.py
│   │   ├── task.py
│   │   ├── message.py
│   │   └── ...
│   ├── schemas/                 # Pydantic Schemas (Request/Response)
│   ├── routers/                 # FastAPI Router
│   │   ├── sessions.py
│   │   ├── tasks.py
│   │   ├── chat.py
│   │   ├── safety.py
│   │   ├── verification.py
│   │   └── config.py
│   ├── services/                # Business Logic
│   │   ├── session_service.py
│   │   ├── timer_service.py
│   │   ├── task_service.py
│   │   ├── safety_service.py
│   │   ├── media_service.py
│   │   └── ai_gateway.py        # KI-Abstraktion
│   ├── templates/               # Jinja2 HTML-Templates
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   ├── chat.html
│   │   ├── tasks.html
│   │   ├── config.html
│   │   └── partials/
│   └── static/
│       ├── css/
│       └── js/
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
- Das Frontend verwendet `<input type="file" capture="environment">` ohne Download-Attribut; nach dem Upload hat der Client keine Kopie
- Server speichert Fotos ausschliesslich im `data/media/`-Verzeichnis des Backend-Servers
- Dateinamen sind nicht erratbar (UUID-basiert)
- Das `data/`-Verzeichnis ist in `.gitignore` eingetragen
- Fotos werden nicht als Inline-Bild an den Client zurückgeliefert; nur eine Bestätigung und das KI-Analyse-Ergebnis werden zurückgegeben

### Sessions-Integrität
- Safety-Endpoints sind gesondert und haben höchste Priorität
- Emergency Release schreibt immer ins Safety-Log, auch bei Fehlern

---

## KI-Gateway Abstraktion

```python
# Abstraktes Interface – erlaubt einfachen Wechsel des KI-Backends
class AIGateway(ABC):
    async def chat(self, messages: list[Message], persona: Persona) -> str: ...
    async def analyze_image(self, image_path: str, context: str) -> str: ...

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
