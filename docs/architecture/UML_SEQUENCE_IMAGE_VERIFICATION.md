````markdown
# UML - Sequence: Image Verification

Sequenz fuer den Bildpruefungs-Workflow aus der Action-Card.

```mermaid
sequenceDiagram
    actor Wearer
    participant UI as Chat UI
    participant ChatAPI as API /chat/vision-review
    participant FS as Image Storage (data/image_verifications)
    participant AI as Vision Model
    participant Parser as Action Parser
    participant DB as SQL DB

    Wearer->>UI: "Bild aufnehmen" und Datei/Kamera waehlen
    UI->>UI: DataURL erzeugen + Vorschau anzeigen
    Wearer->>UI: "Bild prüfen"
    UI->>ChatAPI: POST /api/v1/chat/vision-review (picture_data_url, instruction)

    ChatAPI->>ChatAPI: Bild validieren (MIME, Base64, Groesse)
    ChatAPI->>FS: Bild persistieren (Audit/Tracing)
    ChatAPI->>AI: Vision-Review Prompt senden
    AI-->>ChatAPI: kurze Bewertung (PASSED/FAILED)

    ChatAPI->>Parser: extract_pending_actions(narration)
    Parser-->>ChatAPI: cleaned_narration + optional actions
    ChatAPI->>DB: Turn persistieren
    ChatAPI-->>UI: narration + pending/executed/failed actions
```

## Kernregeln

- Output ist auf kurze Bewertung reduziert (ohne separate Bildbeschreibung).
- Roh-Tags wie `[[REQUEST...]]` werden nicht im UI angezeigt.
- Bilddaten werden serverseitig groessenbegrenzt verarbeitet.

````
