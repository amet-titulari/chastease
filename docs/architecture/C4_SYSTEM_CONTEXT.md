# C4 - System Context

Dieses Diagramm zeigt das Chastease-System aus externer Sicht.

```mermaid
flowchart LR
    Player["Spieler:in"] -->|Spielt, trifft Entscheidungen| WebClient["Web Client (SPA)"]
    WebClient -->|HTTPS JSON API| Chastease["Chastease Plattform"]
    Chastease -->|LLM Requests| OpenAI["OpenAI API"]
    Chastease -->|Persistenz| Postgres["PostgreSQL"]
    Admin["Content/Admin Team"] -->|Pflegt Spielinhalte| AdminUI["Admin UI (spaeter)"]
    AdminUI -->|HTTPS JSON API| Chastease
```

## Kontextgrenzen

- Innerhalb Systemgrenze: Chastease Plattform (Backend + Fachlogik)
- Ausserhalb Systemgrenze: Spieler:innen, OpenAI API, Datenbankbetrieb, spaeter Admin-Clients
