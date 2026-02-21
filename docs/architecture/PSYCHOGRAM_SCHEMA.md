# Psychogramm Schema (MVP)

Dieses Dokument beschreibt das strukturierte Psychogramm, das waehrend des Setup-Prozesses aus den Fragebogenantworten erzeugt wird.

## Ziel

- Bereitstellung relevanter Informationen ueber Vorlieben und Abneigungen des Wearers fuer den KI-Keyholder
- Schaerfung des KI-Charakterprofils (`Keyholder`) pro Session
- bessere Kalibrierung von Tonfall, Intensitaet, Kontrollhaeufigkeit und Eskalationslogik
- konsistente, auditierbare Ableitung statt freier Ad-hoc-Interpretation

Hinweis:
- Das Psychogramm ist ein Interaktions- und Praeferenzprofil fuer die Sessionsteuerung, keine klinische Diagnose.

## Datenmodell

Psychogramm-Objekt je Session:

- `psychogram_version` (string)
- `created_at` (ISO timestamp)
- `source_questionnaire_version` (string)
- `consent_scope` (object)
- `traits` (object)
- `limits` (object)
- `interaction_preferences` (object)
- `risk_flags` (array of string)
- `confidence` (0.0 - 1.0)
- `summary` (short text)

## Felddefinitionen

### consent_scope

- `allowed_topics` (string[])
- `forbidden_topics` (string[])
- `reflection_transparency` (enum: `none`, `partial`, `full`)
- `hard_stop_enabled` (boolean)

### traits

Normierte Wertebereichsskala `0-100`:

- `structure_need` (Beduerfnis nach klaren Regeln)
- `strictness_affinity` (Praeferenz fuer Strenge)
- `challenge_affinity` (Praeferenz fuer Herausforderungen)
- `praise_affinity` (Praeferenz fuer positive Bestaerkung)
- `accountability_need` (Beduerfnis nach Kontrolle/Verbindlichkeit)
- `novelty_affinity` (Praeferenz fuer Abwechslung)

### limits

- `max_intensity_level` (1-5)
- `max_penalty_per_day_minutes` (integer)
- `max_penalty_per_week_minutes` (integer)
- `allowed_opening_types` (string[])
- `blocked_action_types` (string[])

### interaction_preferences

- `preferred_tone` (enum: `soft`, `balanced`, `strict`)
- `feedback_style` (enum: `short`, `balanced`, `detailed`)
- `control_request_style` (enum: `direct`, `contextual`, `gentle`)
- `suggest_mode_bias` (0-100)  
  0 = stark `execute`, 100 = stark `suggest`

## Scoring-Logik (MVP)

1. Jede Frage wird einem oder mehreren `traits` mit Gewicht zugeordnet.  
2. Rohwerte werden auf `0-100` normalisiert.  
3. Harte Limits aus direkten Grenzfragen ueberschreiben abgeleitete Vorschlaege.  
4. Bei widerspruechlichen Antworten:
- `risk_flags` setzen
- `confidence` reduzieren
- konservative Policy-Werte verwenden

## Ableitung fuer KI-Profil

Aus dem Psychogramm wird ein `ai_profile_patch` fuer die Session erstellt:

- Tonalitaet (`preferred_tone`)
- Intensitaetskorridor (`max_intensity_level`)
- Kontrollhaeufigkeit/Art (`accountability_need`, `control_request_style`)
- Verstaerkungsstil (`praise_affinity`, `feedback_style`)
- Aktionspraeferenzen und Blocklisten (`allowed_opening_types`, `blocked_action_types`)

Zweck:
- Die KI versteht den Wearer besser und gestaltet Verlauf und Interaktion interessanter, passender und konsistenter.

## JSON Beispiel

```json
{
  "psychogram_version": "1.0.0",
  "created_at": "2026-02-21T10:30:00Z",
  "source_questionnaire_version": "setup-q-v1",
  "consent_scope": {
    "allowed_topics": ["discipline", "routine", "accountability"],
    "forbidden_topics": ["public_exposure"],
    "reflection_transparency": "partial",
    "hard_stop_enabled": true
  },
  "traits": {
    "structure_need": 82,
    "strictness_affinity": 67,
    "challenge_affinity": 74,
    "praise_affinity": 45,
    "accountability_need": 88,
    "novelty_affinity": 53
  },
  "limits": {
    "max_intensity_level": 3,
    "max_penalty_per_day_minutes": 45,
    "max_penalty_per_week_minutes": 180,
    "allowed_opening_types": ["hygiene"],
    "blocked_action_types": []
  },
  "interaction_preferences": {
    "preferred_tone": "balanced",
    "feedback_style": "short",
    "control_request_style": "direct",
    "suggest_mode_bias": 30
  },
  "risk_flags": [],
  "confidence": 0.84,
  "summary": "Struktur- und Accountability-orientiert, mittlere Strenge, klare Grenzen."
}
```

## Validierungsregeln

- Pflichtfelder duerfen nicht `null` sein.
- `confidence < 0.5` erzwingt konservative Session-Defaults.
- `blocked_action_types` hat Vorrang vor allen anderen Ableitungen.
- `hard_stop_enabled=true` muss in Session-Policy gespiegelt sein.
