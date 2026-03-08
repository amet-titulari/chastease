# Plomben-Steuerung: UI/Frontend Integration

Diese Dokumentation beschreibt die erforderlichen Frontend-Änderungen für die Plomben-Steuerung in Chastease.

## Setup Flow

### 1. Seal-Modus Auswahlfeld hinzufügen

**Wo**: Setup-Formular (setup.js / setup.html)

**Feld**:
```html
<div class="form-group">
  <label for="seal_mode">Plomben/Siegelung:</label>
  <select id="seal_mode" name="seal_mode">
    <option value="none">Keine (Freie Hygieneöffnungen)</option>
    <option value="plomben">Tagebuch-Stil (Nummern erforderlich)</option>
    <option value="versiegelung">Vollständige Siegelung</option>
  </select>
  <small>Wenn aktiviert: Bei jeder Hygieneöffnung muss die sichere Nummer eingegeben werden</small>
</div>
```

### 2. Setup-Start mit seal_mode

```javascript
// In setup.js
const payload = {
  user_id: userId,
  auth_token: authToken,
  seal_mode: document.getElementById('seal_mode').value || 'none'
};

POST /setup/sessions
{
  ...
  seal_mode: "plomben"
}
```

### 3. Nachträgliche Änderung (Optional)

```javascript
// POST /setup/sessions/{setup_session_id}/seal
{
  user_id: userId,
  auth_token: authToken,
  seal_mode: "plomben"
}
```

## Chat / Session Flow

### 1. Seal-Informationen im Chat anzeigen (Optional)

```javascript
// In chat.js
// Nach /chat/turn Antwort

if (response.session_info && response.session_info.seal_mode !== 'none') {
  const sealInfo = response.session_info.runtime_seal;
  console.log(`Plombe Status: ${sealInfo.status}`);
  if (sealInfo.needs_new_seal) {
    console.log('⚠️ Neue Plombennummer erforderlich beim Schließen!');
  }
}
```

### 2. Hygiene-Schließung mit Plombe

**Conditionales Formularfeld**:

```javascript
// In chat.js (bei hygiene_close Action)

const isSealRequired = sessionState.seal_mode !== 'none';

if (isSealRequired) {
  // Eingabefeld für Plombennummer anzeigen
  const sealInput = document.createElement('input');
  sealInput.type = 'text';
  sealInput.placeholder = 'Neue Plombennummer (min. 3 Zeichen)';
  sealInput.id = 'seal_text_input';
  // ... in UI rendern
}
```

**Action-Ausführung**:

```javascript
const payload = {};
if (isSealRequired) {
  const sealText = document.getElementById('seal_text_input').value.trim();
  if (sealText.length < 3) {
    alert('Plombennummer muss mind. 3 Zeichen lang sein');
    return;
  }
  payload.seal_text = sealText;
}

POST /chat/actions/execute
{
  session_id: sessionId,
  action_type: 'hygiene_close',
  payload: payload  // { seal_text: "PLOMBE-02" } oder {}
}
```

### 3. Hygiene-Öffnung (Keine UI-Änderung nötig)

Die Öffnung funktioniert gleich wie zuvor:

```javascript
POST /chat/actions/execute
{
  session_id: sessionId,
  action_type: 'hygiene_open',
  payload: {}
}
```

### 4. Offene Pending-Aktionen abfragen

Sowohl Frontend als auch AI koennen offene, noch nicht aufgeloeste Aktionen explizit abfragen:

```javascript
GET /api/v1/chat/pending/{session_id}?auth_token=<token>
```

Response:

```json
{
  "session_id": "sess_123",
  "total": 2,
  "pending_actions": [
    {
      "action_id": "0d9b4a8db2f7d8f1d6e94a41",
      "event_id": "evt_abc",
      "turn_id": "turn_xyz",
      "turn_no": 48,
      "action_type": "hygiene_open",
      "payload": {
        "reason": "Neue Plombe eintragen Hygiene"
      },
      "detail": "Waiting for execute confirmation.",
      "created_at": "2026-03-08T10:15:00Z",
      "expected_status": "pending"
    }
  ]
}
```

Hinweise:

- `action_id` ist die stabile OCC-Referenz fuer eine konkrete Pending-Action.
- `turn_no` kann im UI oder in der AI-Narration verwendet werden, um den Ursprung der offenen Aktion klar zu benennen.
- Fuer AI-Zugriffe kann alternativ `ai_access_token` verwendet werden.

### 5. Pending-Aktionen manuell aufloesen (OCC)

Das Activity-Log kann offene Aktionen manuell als `success` oder `failed` markieren.
Die Aufloesung verwendet Optimistic Concurrency Control: Die Mutation wird nur akzeptiert, wenn die Action noch im erwarteten Zustand `pending` ist.

```javascript
POST /api/v1/chat/actions/resolve
{
  "session_id": "sess_123",
  "action_id": "0d9b4a8db2f7d8f1d6e94a41",
  "resolution_status": "success",
  "expected_status": "pending",
  "note": "Manuell bestaetigt nach externer Pruefung"
}
```

Response:

```json
{
  "resolved": true,
  "session_id": "sess_123",
  "action_id": "0d9b4a8db2f7d8f1d6e94a41",
  "status": "success",
  "message": "Pending action manually marked as success."
}
```

Fehlerfall:

- `409 Conflict`, wenn die Aktion zwischenzeitlich bereits ausgefuehrt, fehlgeschlagen oder anderweitig aufgeloest wurde
- keine direkte Mutation historischer Audit-Zeilen; stattdessen entsteht ein neuer Resolve-Audit-Event

## Dashboard / Übersicht (Optional)

```javascript
// Zeige aktuellen Plomben-Status

GET /chat/seal/{session_id}?ai_access_token=<token>

// Response verarbeiten
{
  seal_mode: "plomben",
  runtime_seal: {
    status: "sealed",
    current_text: "PLOMBE-ALPHA-01",
    sealed_at: "2026-03-01T12:30:00Z",
    needs_new_seal: false
  }
}

// UI:
if (response.runtime_seal) {
  console.log(`Status: ${response.runtime_seal.status}`);
  console.log(`Aktuelle Nummer: ${response.runtime_seal.current_text}`);
  if (response.runtime_seal.needs_new_seal) {
    console.log('⚠️ ERNEUERUNG ERFORDERLICH');
  }
}
```

## Validierung

- **Seal-Text Mindestlänge**: 3 Zeichen (JavaScript + Server)
- **Pflichtfeld**: Nur wenn `seal_mode !== 'none'` und `action_type = 'hygiene_close'`
- **Error-Handling**: API (v1.1.1+) gibt 400 zurück, wenn seal_text fehlt/zu kurz ist
- **OCC fuer manuelle Aufloesung**: API gibt 409 zurueck, wenn `expected_status="pending"` nicht mehr stimmt

## Responsive Verhalten

| Szenario | Verhalten |
|---|---|
| Setup: seal_mode = "none" | Kein Eingabefeld im Chat |
| Chat: hygiene_close ohne seal_ttext | HTTP 400 Error (mit seal_mode aktiv) |
| Chat: Neue Nummer eingegeben | Wird in runtime_seal.current_text gespeichert |
| Chat: status = "broken" | UI kann Warnung anzeigen |

## Testing

### Manual Test (Curl)

```bash
# Setup mit Plomben starten
curl -X POST http://localhost:8000/api/v1/setup/sessions \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","auth_token":"test123456","seal_mode":"plomben"}'

# Seal-Modus ändern
curl -X POST http://localhost:8000/api/v1/setup/sessions/{id}/seal \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","auth_token":"test123456","seal_mode":"plomben"}'

# Seal-Status abrufen (während Session)
curl http://localhost:8000/api/v1/chat/seal/{session_id}?ai_access_token=<token>
```

### Unit Test (Python)

```python
# tests/test_seal_control.py

def test_setup_seal_mode_accepted():
    # Überprüfe, dass seal_mode akzeptiert wird
    pass

def test_hygiene_close_requires_seal_text_when_enabled():
    # Überprüfe, dass seal_text erforderlich ist
    pass

def test_hygiene_close_seal_text_stored():
    # Überprüfe, dass neue Nummer gespeichert wird
    pass

def test_get_seal_status_api():
    # Überprüfe, dass GET /chat/seal/{id} funktioniert
    pass
```

## Deployment Notes

- **Datenbank-Migration**: Nicht erforderlich (seal_mode bereits in schema)
- **Environment Variables**: `AI_SESSION_READ_TOKEN` muss fuer AI-Lesezugriffe auf `GET /chat/seal/{session_id}` und `GET /chat/pending/{session_id}` gesetzt sein
- **Abwärts-Kompatibilität**: seal_mode="none" ist Standard (keine Plomben)
- **Versionierung**: API v1.1.1 (Seal-Support)
