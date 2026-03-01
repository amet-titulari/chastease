# Seal / Plomben-Steuerung (API)

Dieses Dokument beschreibt die API und Steuerungslogik für Plomben/Siegelungen im Chastease-System.

## Konzept

**Plomben (Seal)** sind Tagebuch-ähnliche Nummern, die bei Hygieneschließungen gespeichert werden. Sie dienen als Verifizierungsmechanismus, dass ein physisches Siegel oder eine Plombe tatsächlich intakt ist.

- **Mit Plomben**: Die aktuelle Nummer muss bei jeder Hygieneöffnung korrekt eingegeben werden
- **Ohne Plomben**: Die Hygieneöffnung ist unkontrolliert möglich

## Setup / Basis-Konfiguration

### Seal-Modi

Die Plomben-Steuerung hat drei Modi:

| Modus | Beschreibung | Seal-Text erforderlich? |
|---|---|---|
| `none` | Keine Plomben aktiviert | ❌ Nein |
| `plomben` | Tagebuch-Style Siegelung | ✅ Ja (bei `hygiene_close`) |
| `versiegelung` | Volle Siegelung | ✅ Ja (bei `hygiene_close`) |

### Steuerung im Setup

**Zeitpunkt**: Der Seal-Modus wird während der Setup-Phase konfiguriert.

**API Endpoints**:

1. **Setup-Start** (POST `/setup/sessions`)
   ```json
   {
     "user_id": "...",
     "auth_token": "...",
     "seal_mode": "plomben"
   }
   ```

2. **Nachträgliche Änderung** (POST `/setup/sessions/{setup_session_id}/seal`)
   ```json
   {
     "user_id": "...",
     "auth_token": "...",
     "seal_mode": "plomben"
   }
   ```
   
   Antwort:
   ```json
   {
     "setup_session_id": "...",
     "status": "setup_in_progress",
     "seal_mode": "plomben",
     "applied_to_active_session": false
   }
   ```

## Runtime / Während einer aktiven Session

### Policy-Struktur

Die `policy` enthält die aktuellen Seal-Informationen:

```json
{
  "seal": {
    "mode": "plomben",
    "required_on_close": true
  },
  "runtime_seal": {
    "status": "sealed",
    "current_text": "PLOMBE-ALPHA-01",
    "sealed_at": "2026-03-01T12:30:00Z",
    "broken_at": null,
    "needs_new_seal": false
  }
}
```

### Seal-Zustände

| Status | Bedeutung | Nächste Aktion |
|---|---|---|
| `sealed` | Plombe ist versiegelt | Nummer muss bei `hygiene_close` eingegeben werden |
| `broken` | Plombe wurde gebrochen (nach `hygiene_open`) | Neue Nummer muss bei `hygiene_close` eingegeben werden |
| `none` | Keine Plombre aktiv (seal_mode=none) | Keine Eingabe erforderlich |

### Hygiene-Workflow

**1. Hygiene-Öffnung** (`hygiene_open`)
```
VORHER: runtime_seal.status = "sealed", current_text = "PLOMBE-ALPHA-01"
          ↓
          Öffnung wird durchgeführt
          ↓
NACHHER: runtime_seal.status = "broken", needs_new_seal = true
```

**2. Hygiene-Schließung** (`hygiene_close`)
- **Ohne Plomben** (seal_mode=none): Keine Eingabe erforderlich
- **Mit Plomben**: `seal_text` (min. 3 Zeichen) mit neuer Plombennummer erforderlich
  
```
VORHER: runtime_seal.status = "broken", needs_new_seal = true
          ↓
          seal_text = "PLOMBE-ALPHA-02" wird eingegeben
          ↓
NACHHER: runtime_seal.status = "sealed", current_text = "PLOMBE-ALPHA-02"
         sealed_at = <current_timestamp>, needs_new_seal = false
```

## KI-Integration

### Seal-Informationen abrufen

Die KI kann die aktuellen Plomben-Informationen auf zwei Wegen erhalten:

#### 1. Implizit über Psychogramm-Summary
Im `psychogram_summary`, den die KI mit jedem Request erhält:

```
seal=mode=plomben, status=sealed, current_number=PLOMBE-ALPHA-01
```

#### 2. Explizit über API (GET `/chat/seal/{session_id}`)

```bash
GET /api/v1/chat/seal/{session_id}?ai_access_token=<token>
```

Antwort:
```json
{
  "session_id": "...",
  "seal_mode": "plomben",
  "runtime_seal": {
    "status": "sealed",
    "current_text": "PLOMBE-ALPHA-01",
    "sealed_at": "2026-03-01T12:30:00Z",
    "broken_at": null,
    "needs_new_seal": false
  }
}
```

### KI-Logik basierend auf Seal-Status

Die KI sollte:

1. **Bei status=sealed**: 
   - Wearer kann Hygienöffnung beantragen
   - KI kann vorschlagen, neue Nummer zu setzen, wenn das Siegel „verdächtig" aussieht

2. **Bei status=broken**:
   - Wearer muss neue Nummer eingeben, bevor Lock wieder geschlossen wird
   - KI kann diesen Prozess mit Erzählung unterstützen

3. **Bei needs_new_seal=true**:
   - KI kann den Wearer an fehlende Eingabe erinnern
   - KI kann Story erzählen, bis Nummer eingegeben ist

## Sicherheit & Auditierung

- **Änderungen am Seal-Modus**: Werden in der aktiven Session sofort angewendet (via `sync_setup_snapshot_to_active_session`)
- **Seal-Text-Input**: Wird auditiert als Action mit vollständigem Payload
- **Tamper-Schutz**: Der Wearer kann die Nummer nicht ändern, wenn das Siegel noch versiegelt ist (nur bei `hygiene_close` möglich)

## Beispiele

### Beispiel 1: Mit Plomben spielen

**Setup**:
```json
{
  "seal_mode": "plomben"
}
```

**Laufzeit - Hygiene-Öffnung**:
```bash
POST /api/v1/chat/actions/execute
{
  "session_id": "...",
  "action_type": "hygiene_open",
  "payload": {}
}
```

**Laufzeit - Hygiene-Schließung (mit Plombe)**:
```bash
POST /api/v1/chat/actions/execute
{
  "session_id": "...",
  "action_type": "hygiene_close",
  "payload": {
    "seal_text": "PLOMBE-BETA-02"
  }
}
```

### Beispiel 2: Ohne Plomben spielen

**Setup**:
```json
{
  "seal_mode": "none"
}
```

**Laufzeit - Hygiene-Schließung (ohne Plombe)**:
```bash
POST /api/v1/chat/actions/execute
{
  "session_id": "...",
  "action_type": "hygiene_close",
  "payload": {}
}
```
Kein `seal_text` erforderlich! ✅

## Frontend-Integration

Die UI sollte:
1. Im Setup-Flow ein Feld für `seal_mode` anzeigen
2. Bei `hygiene_close` ein Text-Eingabefeld für `seal_text` anzeigen (nur wenn seal_mode != "none")
3. Den aktuellen Plomben-Status im Chat/Dashboard anzeigen (optional)
