# UML - Sequence: Setup Lifecycle

Sequenz fuer den Setup-Flow mit stabilem Statuspfad:
`draft -> setup_in_progress -> configured`.

```mermaid
sequenceDiagram
    actor Wearer
    participant UI as Web UI (/app)
    participant SessionsAPI as API /sessions
    participant SetupAPI as API /setup
    participant Store as setup_sessions.json
    participant DB as SQL DB
    participant AI as AI Service

    Note over Wearer,AI: Einstieg / Login
    Wearer->>UI: Login oder Registrierung
    UI->>SessionsAPI: GET /api/v1/sessions/active
    SessionsAPI->>Store: find_or_create_draft_setup_session(user_id)
    SessionsAPI-->>UI: has_active_session=false, setup_session_id, setup_status=draft

    Note over Wearer,AI: Konfiguration frei in draft
    Wearer->>UI: Setup-Felder bearbeiten
    Wearer->>UI: "Speichern"
    UI->>SetupAPI: POST /api/v1/setup/sessions
    SetupAPI->>Store: lade draft/setup_in_progress
    SetupAPI->>Store: persistiere Konfiguration, status=setup_in_progress
    SetupAPI-->>UI: setup_session_id, status=setup_in_progress, questions

    Wearer->>UI: Psychogramm-Antworten senden
    UI->>SetupAPI: POST /api/v1/setup/sessions/{id}/answers
    SetupAPI->>Store: validiere + persistiere answers/psychogram/policy_preview
    SetupAPI-->>UI: answered_questions, psychogram_preview

    Wearer->>UI: "Complete Setup" bestaetigen
    UI->>SetupAPI: POST /api/v1/setup/sessions/{id}/complete
    SetupAPI->>Store: status=configured, active_session_id=None
    SetupAPI-->>UI: status=configured, artifacts_status=pending

    Note over Wearer,AI: Aktivierung erst nach erfolgreicher AI-Pruefung
    UI->>SetupAPI: POST /api/v1/setup/sessions/{id}/artifacts
    SetupAPI->>AI: Psychogramm-Analyse generieren
    SetupAPI->>AI: Vertrag auf Basis Template + Psychogramm generieren
    SetupAPI->>DB: ChastitySession(status=active) anlegen (wenn erfolgreich)
    SetupAPI->>Store: generated_contract + analysis persistieren
    SetupAPI->>DB: policy/psychogram snapshot + system turn persistieren
    SetupAPI-->>UI: status=ready, session_id

    Note over Wearer,AI: Setup ist ab configured gesperrt
```

## Statusregeln

- `draft`:
  - Setup-Session existiert immer (mindestens) in diesem Status.
  - Setup-Eingaben sind editierbar.
- `setup_in_progress`:
  - Konfiguration gespeichert, Fragebogen aktiv.
  - Setup-Eingaben bleiben editierbar.
- `configured`:
  - Setup ist abgeschlossen, aber noch nicht aktiv.
  - Aktivierung erfolgt erst nach erfolgreicher Artefakt-Generierung durch die AI.
  - Setup-Eingaben sind gesperrt.
