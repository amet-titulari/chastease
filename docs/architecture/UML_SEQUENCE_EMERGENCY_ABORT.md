````markdown
# UML - Sequence: Emergency Abort

Sequenz fuer den Notfallabbruch inkl. direkter `ttlock_open`-Notfalloeffnung.

```mermaid
sequenceDiagram
    actor Wearer
    participant UI as Chat UI
    participant ChatAPI as API /chat/turn
    participant Abort as Abort Handler
    participant Gateway as Action Gateway
    participant TTLock as TTLock API
    participant Store as setup_sessions.json
    participant DB as SQL DB

    Wearer->>UI: Notfallsignal (z. B. "rot", "abbrechen", Safeword)
    UI->>ChatAPI: POST /api/v1/chat/turn
    ChatAPI->>Abort: Trigger erkennen + runtime_abort anlegen
    Abort-->>ChatAPI: Bestaetigungsanforderung

    Wearer->>UI: Bestaetigungen + Begruendung senden
    UI->>ChatAPI: POST /api/v1/chat/turn
    ChatAPI->>Abort: Protocol pruefen (confirmations/reason)

    alt Abbruch vollstaendig bestaetigt
        Abort-->>ChatAPI: pending_action = ttlock_open(emergency)
        ChatAPI->>Gateway: _auto_execute_pending_actions
        Gateway->>TTLock: unlock (ttlock_open)
        TTLock-->>Gateway: success/failure

        alt unlock erfolgreich
            ChatAPI->>DB: Session status=archived + Contract invalidieren
            ChatAPI->>Store: Setup status=archived + active_session_id entfernen
            ChatAPI-->>UI: Notfall abgeschlossen, Neustart via neues Setup
        else unlock fehlgeschlagen
            ChatAPI-->>UI: Fehlerdetail, Session bleibt aktiv
        end
    else noch nicht bestaetigt
        ChatAPI-->>UI: Hinweis auf fehlende Bestaetigungen/Begruendung
    end
```

## Kernregeln

- Notfallpfad nutzt direkten `ttlock_open`-Mechanismus (kein `hygiene_open`).
- Archivierung/Vertragsinvalidierung nur nach erfolgreicher Oeffnung.
- Bei Unlock-Fehler bleibt die Session aktiv und reproduzierbar.

````
