# UML - Sequence: Hygiene Opening

Sequenz fuer eine regulaere Hygieneoeffnung innerhalb einer aktiven Session.

```mermaid
sequenceDiagram
    actor Wearer
    participant UI as Chat UI
    participant ChatAPI as API /chat/turn
    participant Parser as Action Parser
    participant Gateway as Action Gateway
    participant Policy as Policy Snapshot
    participant Lock as Lock Connector
    participant DB as SQL DB

    Wearer->>UI: Hygieneoeffnung anfragen
    UI->>ChatAPI: POST /api/v1/chat/turn
    ChatAPI->>Parser: extract_pending_actions(narration)
    Parser-->>ChatAPI: pending action hygiene_open

    ChatAPI->>Gateway: auto-execute hygiene_open
    Gateway->>Policy: Preconditions + Limits pruefen

    alt Oeffnung erlaubt
        Gateway->>Lock: hygiene_open(payload)
        Lock-->>Gateway: success
        Gateway-->>ChatAPI: executed_action(hygiene_open)
        ChatAPI->>DB: Turn + Action-Status speichern
        ChatAPI-->>UI: Bestaetigung + verbleibende Zeit
    else Oeffnung nicht erlaubt
        Gateway-->>ChatAPI: failed_action(reason)
        ChatAPI->>DB: Turn + Fehlerstatus speichern
        ChatAPI-->>UI: Ablehnung mit Grund
    end
```

## Kernregeln

- `hygiene_open` ist der regulaere Oeffnungspfad innerhalb einer aktiven Session.
- Limits und Preconditions werden serverseitig geprueft (nicht nur im Frontend).
- Notfallabbruch ist ein separater Pfad und nutzt direkte `ttlock_open`-Logik.
