# Contract Template Pack

This folder contains production-ready contract templates for `Chastease`.

## Files
- `CONTRACT_TEMPLATE_DE.md`: German template with stable clause structure and placeholders.
- `CONTRACT_TEMPLATE_EN.md`: English template with matching structure and placeholders.
- `CONTRACT_TEMPLATE_FIELDS.json`: canonical field list and validation hints.

## Usage
1. Select template by language (`de` or `en`).
2. Fill placeholders using session/setup/policy/psychogram data.
3. Keep clause titles and article order stable for auditability.
4. Never remove safety clauses.

## Runtime recommendation
- Preferred: render template locally with field substitution.
- AI usage: render deterministic draft first, then allow AI to refine wording if needed while keeping article structure and safety clauses intact.
- Fallback: if provider timeout/error occurs, render deterministic output from this template and available fields.

## Safety mode mapping
- `safety_mode = safeword`: provide `safeword`; keep `traffic_light_words` empty.
- `safety_mode = traffic_light`: provide `traffic_light_words`; keep `safeword` empty.
