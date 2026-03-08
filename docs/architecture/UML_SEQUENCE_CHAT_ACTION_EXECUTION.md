````markdown
# UML - Sequence: Chat Action Execution

Sequenz fuer den normalen Chat-Flow mit strukturierten Aktionen und Auto-Execution im `execute`-Modus.

```mermaid
sequenceDiagram
    actor Wearer
    participant UI as Chat UI
    participant ChatAPI as API /chat/turn
    participant AI as AI Service
    participant Parser as Action Parser
    participant Gateway as Action Gateway
    participant Policy as Policy Snapshot
    participant DB as SQL DB

    Wearer->>UI: Nachricht senden
    UI->>ChatAPI: POST /api/v1/chat/turn
    ChatAPI->>DB: Session + Policy laden
    ChatAPI->>AI: Narration erzeugen
    AI-->>ChatAPI: Narration (inkl. optionaler REQUEST-Tags)
    ChatAPI->>Parser: extract_pending_actions(narration)
    Parser-->>ChatAPI: cleaned_narration + pending_actions

    alt autonomy_mode == execute
        ChatAPI->>Gateway: _auto_execute_pending_actions(pending_actions)
        Gateway->>Policy: Preconditions + Payload-Normalisierung
        Gateway-->>ChatAPI: executed_actions / failed_actions / remaining_actions
    else autonomy_mode == suggest
        ChatAPI-->>ChatAPI: pending_actions bleiben offen
    end

    ChatAPI->>DB: Turn + ggf. aktualisierte Policy speichern
    ChatAPI-->>UI: narration + pending/executed/failed actions

    opt Offene Aktionen spaeter pruefen oder manuell aufloesen
        UI->>ChatAPI: GET /api/v1/chat/pending/{session_id}
        ChatAPI->>DB: Audit-Events + Turns lesen
        ChatAPI-->>UI: unresolved pending_actions mit action_id + turn_no
        UI->>ChatAPI: POST /api/v1/chat/actions/resolve
        ChatAPI->>DB: OCC-Pruefung auf status=pending
        ChatAPI->>DB: activity_manual_resolve auditieren
        ChatAPI-->>UI: success oder 409 Conflict
    end
```

## Kernregeln

- Ausfuehrbare Aktionen werden nur ueber das Gateway verarbeitet.
- Bei `suggest` werden keine Side-Effects ausgefuehrt.
- Narration wird um maschinenlesbare Tags bereinigt, bevor sie im UI erscheint.
- Offene Pending-Aktionen koennen spaeter ueber `GET /api/v1/chat/pending/{session_id}` abgefragt werden.
- Manuelle Aufloesung verwendet OCC und erzeugt einen separaten `activity_manual_resolve`-Audit-Event.

````
