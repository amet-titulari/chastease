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
- `updated_at` (ISO timestamp, optional)
- `update_reason` (string, z. B. `initial_setup`, `mid_session_calibration`, `limit_update`)
- `source_questionnaire_version` (string)
- `source_model` (string, z. B. `bdsmtest-inspired`)
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
- `service_orientation` (Praeferenz fuer service-orientierte Aufgaben)
- `protocol_affinity` (Praeferenz fuer Rituale/Protokolle)

### limits

- `max_intensity_level` (1-5)
- `max_penalty_per_day_minutes` (integer)
- `max_penalty_per_week_minutes` (integer)
- `allowed_opening_types` (string[])
- `blocked_action_types` (string[])
- `allowed_challenge_categories` (string[])
  - z. B. `hygiene`, `posture`, `service`, `edge`, `humiliation_light`
- `blocked_trigger_words` (string[])

### interaction_preferences

- `preferred_tone` (enum: `soft`, `balanced`, `strict`)
- `feedback_style` (enum: `short`, `balanced`, `detailed`)
- `control_request_style` (enum: `direct`, `contextual`, `gentle`)
- `autonomy_profile` (enum: `suggest_only`, `suggest_first`, `mixed`, `execute_preferred`)
- `autonomy_bias` (0-100)
  - 0 = stark `execute_preferred`, 100 = stark `suggest_only`
- `praise_timing` (enum: `immediate`, `delayed`, `rare_but_impactful`, `situational`)

## Scoring-Logik (MVP)

1. Jede Frage wird einem oder mehreren `traits` mit Gewicht zugeordnet.  
2. Fragebogenwerte (`1-10`) werden auf `0-100` normalisiert.  
3. Harte Limits aus direkten Grenzfragen ueberschreiben abgeleitete Vorschlaege.  
4. Bei widerspruechlichen Antworten:
- `risk_flags` setzen
- `confidence` reduzieren
- konservative Policy-Werte verwenden

5. Dynamische Nachkalibrierung:
- bei neuen Erkenntnissen (`update_reason`) darf das Psychogramm aktualisiert werden
- jedes Update setzt `updated_at` und wird auditierbar protokolliert

## Ableitung fuer KI-Profil

Aus dem Psychogramm wird ein `ai_profile_patch` fuer die Session erstellt:

- Tonalitaet (`preferred_tone`)
- Intensitaetskorridor (`max_intensity_level`)
- Kontrollhaeufigkeit/Art (`accountability_need`, `control_request_style`)
- Verstaerkungsstil (`praise_affinity`, `feedback_style`)
- Aktionspraeferenzen und Blocklisten (`allowed_challenge_categories`, `blocked_action_types`, `blocked_trigger_words`)

Zweck:
- Die KI versteht den Wearer besser und gestaltet Verlauf und Interaktion interessanter, passender und konsistenter.

## JSON Beispiel

```json
{
  "psychogram_version": "2.0.0",
  "created_at": "2026-02-21T10:30:00Z",
  "updated_at": null,
  "update_reason": "initial_setup",
  "source_questionnaire_version": "setup-q-v2",
  "source_model": "bdsmtest-inspired",
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
    "novelty_affinity": 53,
    "service_orientation": 64,
    "protocol_affinity": 71
  },
  "limits": {
    "max_intensity_level": 3,
    "max_penalty_per_day_minutes": 45,
    "max_penalty_per_week_minutes": 180,
    "allowed_opening_types": ["hygiene"],
    "blocked_action_types": [],
    "allowed_challenge_categories": ["hygiene", "service", "posture"],
    "blocked_trigger_words": ["public", "workplace"]
  },
  "interaction_preferences": {
    "preferred_tone": "balanced",
    "feedback_style": "short",
    "control_request_style": "direct",
    "autonomy_profile": "mixed",
    "autonomy_bias": 45,
    "praise_timing": "rare_but_impactful"
  },
  "risk_flags": [],
  "confidence": 0.84,
  "summary": "Struktur- und Accountability-orientiert, mittlere Strenge, klare Grenzen."
}
```

## Validierungsregeln

- Pflichtfelder duerfen nicht `null` sein.
- `confidence < 0.5` erzwingt konservative Session-Defaults:
  - `tone=balanced`
  - `max_intensity_level=2`
  - `autonomy_profile=suggest_first`
  - `autonomy_bias=80`
  - `max_penalty_per_day_minutes=20`
- `blocked_action_types` hat Vorrang vor allen anderen Ableitungen.
- `hard_stop_enabled=true` muss in Session-Policy gespiegelt sein.
