# UML - Sequence: Story Turn

Sequenz fuer den zentralen Gameplay-Flow "Spieleraktion -> KI-Reaktion -> Persistenz".

```mermaid
sequenceDiagram
    actor Player as Spieler:in
    participant Client as Web Client
    participant API as Python API
    participant Rules as Rule Engine
    participant AI as AI Service
    participant DB as PostgreSQL

    Player->>Client: Gibt Aktion ein
    Client->>API: POST /api/v1/story/turn
    API->>DB: Lade Session + session_state + Character
    DB-->>API: Aktueller Zustand
    API->>Rules: Evaluiere Regelwirkung (Checks/Folgen)
    Rules-->>API: Regelresultat
    API->>AI: Erzeuge Narration mit Kontext
    AI-->>API: Narration + strukturierte Folgehinweise
    API->>DB: Speichere Turn + aktualisiere session_state
    DB-->>API: Persistenz ok
    API-->>Client: 200 Response mit Narration + Zustand
    Client-->>Player: Anzeige der neuen Spielsituation
```

## Wichtige Varianten

- KI-Timeout: API liefert degradierte Antwort mit rein regelbasierter Narration.
- Ungueltige Aktion: API validiert und gibt 400 mit Fehlerdetails zurueck.
