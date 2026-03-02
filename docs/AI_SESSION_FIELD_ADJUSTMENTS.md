# KI-gesteuerte Feldanpassungen während der Sitzung

## Übersicht

Während einer aktiven Chastity-Sitzung kann die KI bestimmte Konfigurationsfelder dynamisch anpassen, um das Rollenspiel zu optimieren. Diese Felder sind:

### 1. POLICY-FELDER (Session-Verhalten)
- **contract_min_end_date**: Mindestdauer der Vereinbarung
- **opening_limit_period**: Zeitraum für Öffnungs-Limitierungen (day/week/month)
- **max_openings_in_period**: Maximale Anzahl von Öffnungen pro Zeitraum
- **opening_window_minutes**: Dauer des Öffnungs-Fensters in Minuten
- **seal_mode**: Versiegelungsmodus (none/plomben/versiegelung)
- **initial_seal_number**: Erste Plombennummer
- **max_intensity_level**: Intensität der Session (1-5 Skala, kann unabhängig von strictness_affinity angepasst werden)

### 2. PSYCHOGRAMM-TRAITS (Präferenzen/Persönlichkeit)
Diese basieren auf den Antworten des Psychogramms, können aber von der KI während der Session angepasst werden, wenn sie neue Informationen vom Träger erhält:
- **structure_need**: Wie wichtig sind klare, schriftliche Regeln und Erwartungen
- **strictness_affinity**: Wie stark will der Träger Strenge und Konsequenz erleben
- **challenge_affinity**: Wie sehr will der Träger Herausforderungen für seine Fähigkeiten
- **praise_affinity**: Wie wichtig ist positives Feedback und Anerkennung
- **accountability_need**: Wie sehr braucht der Träger sich kontrolliert und überwacht zu fühlen
- **novelty_affinity**: Wie sehr sucht der Träger Abwechslung und neue Aufgaben
- **service_orientation**: Wie gerne erbringt der Träger Dienste/Aufgaben
- **protocol_affinity**: Wie wichtig sind formale Protokolle und Prozeduren

## Zugriff für Benutzer

### Während Setup
- Diese Felder sind **vollständig editierbar** - der Benutzer gibt die Anfangswerte an

### Während aktiver Session
- Diese Felder sind **read-only** für den Benutzer
- Der Benutzer kann sie in der Session-Ansicht sehen, aber nicht ändern
- Wenn die KI diese Felder anpasst, wird der aktualisierte Wert sofort für den Benutzer sichtbar

## KI-Endpoint zum Aktualisieren

```
POST /api/v1/setup/sessions/{setup_session_id}/ai-update-fields
```

### Request Body

```json
{
  "user_id": "user-uuid",
  "auth_token": "token",
  "updates": {
    "opening_limit_period": "week",
    "max_openings_in_period": 3,
    "opening_window_minutes": 45,
    "max_intensity_level": 4,
    "strictness_affinity": 85,
    "praise_affinity": 42
  },
  "reason": "Psychogramm-Anpassung nach 3 Tagen: Der Träger zeigt höhere Toleranz für Strenge und möchte intensivere Erfahrungen. Intensität erhöht."
}
```

### Response

```json
{
  "setup_session_id": "session-id",
  "message": "AI-controlled fields updated successfully",
  "updated_fields": [
    "opening_limit_period",
    "max_openings_in_period",
    "opening_window_minutes",
    "strictness_affinity",
    "praise_affinity"
  ],
  "policy_updates": {
    "opening_limit_period": "week",
    "max_openings_in_period": 3,
    "opening_window_minutes": 45
  },
  "psychogram_updates": {
    "strictness_affinity": 85,
    "praise_affinity": 42
  },
  "applied_to_active_session": true,
  "setup_session": {
    "psychogram": { ... },
    "policy_preview": { ... }
  }
}
```

## Anwendungsszenarien

### 1. Psychogramm-Kalibrierung basierend auf Beobachtungen
Wenn die KI nach Tagen merkt, dass der Träger anders agiert als im ursprünglichen Psychogramm:
```python
# Beispiel: Der Träger möchte mehr Kontrolle als ursprünglich angegeben
if observed_discipline_score > initial_psychogram.accountability_need + 20:
    updates = {
        "accountability_need": min(100, observed_discipline_score),
        "opening_limit_period": "week",  # Strengere Limitierung
        "max_openings_in_period": 1
    }
    reason = "Beobachtung: Der Träger zeigt höheren Kontrollbedarf als im Psychogramm angegeben"
```

### 2. Öffnungs-Policy Anpassung
Wenn die KI merkt, dass der Träger sehr geduldiger ist oder weniger geduldig:
```python
# KI-Logik
if psychogram.discipline_score > 75 and current_openings_too_restrictive:
    updates = {
        "max_openings_in_period": 4,
        "opening_window_minutes": 60,
        "challenge_affinity": 75  # Der Träger möchte mehr Herausforderung
    }
    reason = "Der Träger zeigt höhere Herausforderungstoleranz"
```

### 3. Versiegelungs-Modus-Verschärfung
Wenn der Träger um strengere Bedingungen bittet oder die KI höhere Kontrolle wünscht:
```python
if intensity_escalation_detected or seal_request_from_user:
    updates = {
        "seal_mode": "versiegelung",
        "initial_seal_number": current_checksum(),
        "max_intensity_level": 5,  # Maximal intensiv
        "strictness_affinity": min(100, current_value + 15)
    }
    reason = "Träger bittet um Maximal-Intensivierung"
```

### 4. Intensität dynamisch basierend auf Reaktionen
Die KI kann die Intensität unabhängig von strictness_affinity anpassen:
```python
# Der Träger zeigt stress Signale → intensität reduzieren
if detected_stress_signals:
    updates = {
        "max_intensity_level": max(1, current_intensity - 1),
        "opening_limit_period": "month"  # Mehr Freiheit
    }
    reason = "Stress-Signale erkannt. Intensität reduziert zur Sicherheit"

# Der Träger wirkt unterfordert/gelangweilt → intensität erhöhen
elif boredom_signals_detected:
    updates = {
        "max_intensity_level": min(5, current_intensity + 1),
        "challenge_affinity": min(100, current_affinity + 15)
    }
    reason = "Träger scheint unterfordert. Intensität und Herausforderung erhöht"
```

### 5. Adaptive Belohnung/Bestrafung
Wenn die KI merkt, dass der Träger weniger an Service interessiert ist, als gedacht:
```python
if user_avoids_service_tasks:
    updates = {
        "service_orientation": max(0, current_value - 20),
        "praise_affinity": min(100, current_value + 10)  # Mehr Lob statt Arbeit
    }
    reason = "Service-Orientierung reduziert, positive Verstärkung erhöht"
```

### 5. Dynamische Regelanpassung
Nach mehreren unerwarteten Reaktionen:
```python
# Die Initiative des Trägers deutet auf weniger Struktur-Bedarf hin
if unexpected_high_initiative:
    updates = {
        "structure_need": max(0, current_value - 15),
        "novelty_affinity": min(100, current_value + 10),
        "protocol_affinity": max(0, current_value - 10)
    }
    reason = "Träger zeigt Interesse an flexibleren, weniger formalen Strukturen"
```

## Sicherheit & Validierung

- **Policy-Felder**:
  - Daten im ISO8601-Format (contract_min_end_date)
  - Enum-Werte für opening_limit_period und seal_mode
  - Numerische Grenzen (0-200 für max_openings_in_period, 1-240 für opening_window_minutes)
  
- **Psychogramm-Traits**:
  - Alle Werte müssen Integers zwischen 0 und 100 sein
  - Keine negativen oder Werte über 100 werden akzeptiert
  - Trait-Namen müssen aus der vordefinierten Liste stammen

- Der `reason`-Parameter dokumentiert, warum die Änderung vorgenommen wurde (optional)

- Änderungen werden im Psychogramm und Session-Snapshot gespeichert mit:
  - `ai_update_timestamp`: Zeitstempel der Änderung  
  - `ai_update_reason`: Grund für die Änderung

## Integration mit Sitzungs-Logik

Wenn die KI diese Felder ändert:
1. **Policy-Felder** werden sofort für den nächsten Story Turn wirksam
2. **Psychogramm-Traits** beeinflussen die Policy-Berechnung (z.B. neue strictness_affinity kann neue Öffnungs-Limitierungen auslösen)
3. Der Benutzer sieht die aktualisierten Werte im Dashboard/Chat-Interface
4. Der Audit Log erfasst die Änderung mit Grund
5. Wenn Psychogramm geändert wird, wird automatisch eine neue Policy-Preview berechnet

## Häufige Muster

### Pattern A: Beobachtungs-basierte Kalibrierung
Nach jedem Story Turn kann die KI prüfen:
- Häufigkeit von Disziplinverstößen → adjust accountability_need
- Art der gewählten Aufgaben → adjust service_orientation/novelty_affinity  
- Reaktion auf Bestrafungen → adjust max_intensity_level + strictness_affinity
- Wiederholte Fragen nach Änderungen → adjust structure_need
- Stress/Langeweile Signale → adjust max_intensity_level

### Pattern B: Eskalation/De-Eskalation
```python
# 3-Stufen-Eskalation mit Intensität
if intensity_level == "low":
    updates = {
        "max_intensity_level": 1,
        "strictness_affinity": 40,
        "challenge_affinity": 30,
        "max_openings_in_period": 3  # Mehr Freiheit
    }
elif intensity_level == "medium":
    updates = {
        "max_intensity_level": 3,
        "strictness_affinity": 70,
        "challenge_affinity": 65,
        "max_openings_in_period": 1  # Weniger Freiheit
    }
elif intensity_level == "high":
    updates = {
        "max_intensity_level": 5,  # Maximum
        "strictness_affinity": 95,
        "challenge_affinity": 90,
        "seal_mode": "versiegelung",
        "opening_window_minutes": 15  # Sehr kurz
    }
```

### Pattern C: Adaptive Belohnung/Bestrafung
```python
# Basierend auf praise_affinity die Häufigkeit anpassen
if psychogram.traits["praise_affinity"] > 70:
    # Mehr Lob ausgeben
elif psychogram.traits["praise_affinity"] < 30:
    # Wenig bis kein Lob, direktere Anweisungen
```
