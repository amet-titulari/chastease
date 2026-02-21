# C4 - Container View

Dieses Diagramm zeigt die zentralen Deploy-/Runtime-Container innerhalb von Chastease.

```mermaid
flowchart TB
    Player["Spieler:in"] --> Web["Web Client (SPA)"]
    Web --> Api["Python API (FastAPI preferred)"]

    Api --> Domain["Domain Layer\nCharacters, World, Quests, Combat, Sessions"]
    Api --> AiService["AI Service Adapter"]
    Api --> Repo["Repository Layer"]

    Repo --> Db[(PostgreSQL)]
    AiService --> OpenAI["OpenAI API"]
    Api --> Queue["Job Queue (Redis/RQ, spaeter)"]
```

## Containerverantwortung

- Web Client:
  - Darstellung, Eingabe, Sessionsteuerung
- Python API:
  - Auth, Orchestrierung, Request/Response, Validierung
- Domain Layer:
  - Spielregeln, Zustandsuebergaenge, Use Cases
- AI Service Adapter:
  - Prompting, Antwortparsing, Guardrails, Fallbacks
- Repository Layer:
  - Datenzugriff und Transaktionsgrenzen
- PostgreSQL:
  - Persistenz von Usern, Charakteren, Sessions, Turns, World State
- Job Queue (spaeter):
  - asynchrone KI- oder Content-Generierungsjobs
