---
template_id: chastity_contract_v1
language: en
format: markdown
render_mode: strict_fill
version: 1.0.1
---

# Chastity Contract

## Article 1: Preamble

This contract governs a voluntary chastity session between the dominant keyholder (hereinafter "Mistress") and the submissive participant (hereinafter "Sub" or "Slave").
It is based on mutual consent, trust, and respect.
The Mistress assumes control over the Sub's chastity to create a dynamic of devotion, anticipation, and psychological intensity.
The Sub acknowledges that this role is a conscious choice.

### Legal and Safety Notice

- This contract is a roleplay and structure agreement.
- It does not replace medical, psychological, or legal advice.
- In case of acute health warning signs, immediate safety stop always applies.

## Article 2: Roles and Responsibilities

### Section 2.1: The Mistress

- Assumes control over the Sub's chastity within the agreed scope.
- Defines rules, tasks, and consequences to foster discipline and awareness.
- Observes the Sub's signals and adjusts intensity and pacing responsibly.
- Uses rewards and consequences precisely, never arbitrarily.

### Section 2.2: The Sub

- Transfers control over chastity within the agreed scope to the Mistress.
- Follows device usage instructions without unauthorized manipulation.
- Communicates physical and emotional state honestly.
- Completes tasks promptly and reflects on process and impact.

## Article 3: Duration and Conditions

- Contract start: ***{{contract_start_date}}***
- Minimum end date: ***{{contract_min_end_date}}***
- Provisional end date (AI): ***{{proposed_end_date_ai}}***
- Maximum end date: ***{{contract_max_end_date}}***
- End date control: ***{{end_date_control_mode}}***
- Adjustment rule: The keyholder may adjust the provisional end date at any time within minimum and maximum end date.

### Additional Conditions

- Minimum duration: ***{{min_duration_days}}*** days
- Maximum extension per incident: ***{{max_extension_per_incident_days}}*** days
- Hard stop: ***{{hard_stop_enabled}}***
- Pause rule (medical/emotional): ***{{pause_policy}}***

## Article 4: Rules and Tasks

### Section 4.1: Operational Rules

- Daily status report: ***{{daily_checkin_required}}***
- Inspection request frequency: ***{{inspection_frequency_policy}}***
- Allowed openings: ***{{max_openings_in_period}}*** per ***{{opening_limit_period}}***
- Maximum opening duration: ***{{opening_window_minutes}}*** minutes

### Section 4.2: Forbidden Actions

- Device manipulation without permission
- Dishonest state reports
- Unilateral abort outside safety rules

### Section 4.3: Rewards and Consequences

- Penalty cap per day: ***{{max_penalty_per_day_minutes}}*** minutes
- Penalty cap per week: ***{{max_penalty_per_week_minutes}}*** minutes
- Reward logic: ***{{reward_policy}}***
- Consequence logic: ***{{penalty_policy}}***

## Article 5: Safety and Boundaries

- Safety mode: ***{{safety_mode}}***
- Safeword (if used): ***{{safeword}}***
- Traffic words (if used): ***{{traffic_light_words}}***
- Hard limits: ***{{hard_limits_text}}***
- Soft limits: ***{{soft_limits_text}}***
- Health protocol: ***{{health_protocol}}***

## Article 6: Psychogram and Interaction Profile

- Psychogram summary: ***{{psychogram_summary}}***
- Instruction style: ***{{instruction_style}}***
- Escalation mode: ***{{escalation_mode}}***
- Experience profile: ***{{experience_profile}}***
- Grooming preference: ***{{grooming_preference}}***
- Tone profile: ***{{tone_profile}}***

## Article 7: Integrations and Runtime Mode

- Integrations: ***{{integrations}}***
- Autonomy mode: ***{{autonomy_mode}}***
- Action execution: ***{{action_execution_mode}}***
- Audit enabled: ***{{audit_enabled}}***

## Article 8: Amendments and Termination

- Contract amendments: ***{{amendment_policy}}***
- Termination rule: ***{{termination_policy}}***
- Debrief rule: ***{{debrief_policy}}***

## Signature

I, ***{{user_name}}***, acknowledge this contract and voluntarily submit to the agreed framework.

- Date: ***{{signature_date_sub}}***
- Sub signature: ***{{signature_sub}}***

I, ***{{keyholder_name}}***, accept this devotion and commit to responsible leadership.

- Date: ***{{signature_date_keyholder}}***
- Mistress signature: ***{{signature_keyholder}}***

Technical Footer:

```json
{
  "template_id": "chastity_contract_v1",
  "language": "en",
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
