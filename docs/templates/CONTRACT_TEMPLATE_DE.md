---
template_id: chastity_contract_v1
language: de
format: markdown
render_mode: strict_fill
version: 1.0.1
---

# Keuschheits-Vertrag

## Artikel 1: Praeambel
Dieser Vertrag regelt eine freiwillige Keuschheits-Sitzung zwischen der dominanten Keyholderin (im Folgenden "Herrin") und dem unterwuerfigen Teilnehmer (im Folgenden "Sub" oder "Sklave").
Er basiert auf gegenseitigem Einverstaendnis, Vertrauen und Respekt.
Die Herrin uebernimmt die Kontrolle ueber die Keuschheit des Subs, um eine Dynamik der Hingabe, Erwartung und psychologischen Intensitaet zu schaffen.
Der Sub erkennt an, dass diese Rolle eine bewusste Wahl ist.

### Rechts- und Safety-Hinweis:
- Dieser Vertrag dient als Rollenspiel- und Strukturvereinbarung.
- Er ersetzt keine medizinische, psychologische oder rechtliche Beratung.
- Bei akuten gesundheitlichen Warnzeichen gilt immer sofortiger Sicherheitsabbruch.

## Artikel 2: Rollen und Verantwortlichkeiten
### Absatz 2.1: Die Herrin
- Uebernimmt die Kontrolle ueber die Keuschheit des Subs im vereinbarten Rahmen.
- Setzt Regeln, Aufgaben und Konsequenzen zur Foerderung von Disziplin und Achtsamkeit.
- Beobachtet Signale des Subs und passt Intensitaet und Tempo verantwortungsvoll an.
- Setzt Belohnungen und Strafen praezise, nicht willkuerlich, ein.

### Absatz 2.2: Der Sub
- Uebergibt die Kontrolle ueber die Keuschheit im vereinbarten Rahmen an die Herrin.
- Beachtet Vorgaben zur Nutzung von Hilfsmitteln ohne unerlaubte Manipulation.
- Kommuniziert koerperlichen und emotionalen Zustand ehrlich.
- Erfuellt Aufgaben zeitnah und reflektiert ueber Verlauf und Wirkung.

## Artikel 3: Dauer und Bedingungen
- Vertragsstart: ***{{contract_start_date}}***
- Mindest-Enddatum: ***{{contract_min_end_date}}***
- Vorlaeufiges Enddatum (KI): ***{{proposed_end_date_ai}}***
- Max-Enddatum: ***{{contract_max_end_date}}***
- Enddatum-Steuerung: ***{{end_date_control_mode}}***
- Regel zur Anpassung: Die Keyholderin darf das vorlaeufige Enddatum jederzeit innerhalb von Mindest- und Max-Enddatum anpassen.

### Weitere Bedingungen:
- Mindestdauer: ***{{min_duration_days}}*** Tage
- Max-Verlaengerung pro Vorfall: ***{{max_extension_per_incident_days}}*** Tage
- Hard-Stop: ***{{hard_stop_enabled}}***
- Pausenregel (medizinisch/emotional): ***{{pause_policy}}***

## Artikel 4: Regeln und Aufgaben
### Absatz 4.1: Regelbetrieb
- Taeglicher Statusbericht: ***{{daily_checkin_required}}***
- Frequenz Kontrollanforderungen: ***{{inspection_frequency_policy}}***
- Erlaubte Oeffnungen: ***{{max_openings_in_period}}*** pro ***{{opening_limit_period}}***
- Maximale Oeffnungsdauer: ***{{opening_window_minutes}}*** Minuten

### Absatz 4.2: Verbotene Handlungen
- Manipulation des Geraets ohne Erlaubnis
- Unehrliche Zustandsmeldungen
- Eigenmaechtiger Abbruch ausserhalb Safety-Regeln

### Absatz 4.3: Belohnungen und Konsequenzen
- Penalty-Cap pro Tag: ***{{max_penalty_per_day_minutes}}*** Minuten
- Penalty-Cap pro Woche: ***{{max_penalty_per_week_minutes}}*** Minuten
- Belohnungslogik: ***{{reward_policy}}***
- Konsequenzlogik: ***{{penalty_policy}}***

## Artikel 5: Sicherheit und Grenzen
- Safety-Modus: ***{{safety_mode}}***
- Safeword (falls genutzt): ***{{safeword}}***
- Ampelbegriffe (falls genutzt): ***{{traffic_light_words}}***
- Harte Grenzen: ***{{hard_limits_text}}***
- Weiche Grenzen: ***{{soft_limits_text}}***
- Gesundheitsprotokoll: ***{{health_protocol}}***

## Artikel 6: Psychogramm und Interaktionsprofil
- Psychogramm-Zusammenfassung: ***{{psychogram_summary}}***
- Instruktionsstil: ***{{instruction_style}}***
- Eskalationsmodus: ***{{escalation_mode}}***
- Erfahrungsprofil: ***{{experience_profile}}***
- Intimrasur-Praeferenz: ***{{grooming_preference}}***
- Tonprofil: ***{{tone_profile}}***

## Artikel 7: Integrationen und Betriebsmodus
- Integrationen: ***{{integrations}}***
- Autonomie-Modus: ***{{autonomy_mode}}***
- Action-Ausfuehrung: ***{{action_execution_mode}}***
- Auditierung aktiv: ***{{audit_enabled}}***

## Artikel 8: Aenderung und Beendigung
- Vertragsaenderungen: ***{{amendment_policy}}***
- Beendigungsregel: ***{{termination_policy}}***
- Debriefing-Regel: ***{{debrief_policy}}***

## Signatur
Ich, ***{{user_name}}***, erkenne diesen Vertrag an und übergebe mich freiwillig in den vereinbarten Rahmen.

- Datum: ***{{signature_date_sub}}***
- Unterschrift Sub: ***{{signature_sub}}***

Ich, ***{{keyholder_name}}***, akzeptiere diese Hingabe und verpflichte mich zu verantwortungsvoller Fuehrung.

- Datum: ***{{signature_date_keyholder}}***
- Unterschrift Herrin: ***{{signature_keyholder}}***

Technischer Footer:
```json
{
  "template_id": "chastity_contract_v1",
  "language": "de",
  "session_id": "{{session_id}}",
  "setup_session_id": "{{setup_session_id}}",
  "version": "{{contract_version}}",
  "generated_at": "{{generated_at_iso}}",
  "generated_by": "{{generated_by}}",
  "consent_required_text": "{{consent_required_text}}",
  "consent_accepted": "{{consent_accepted}}",
  "consent_text": "{{consent_text}}",
  "consent_accepted_at": "{{consent_accepted_at}}"
}
```
