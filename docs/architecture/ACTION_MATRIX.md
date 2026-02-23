# Action Matrix (MVP)

Dieses Dokument definiert, welche Keyholder-Aktionen in welchen Modi erlaubt sind, welche Bedingungen gelten und was verpflichtend auditiert wird.

## Legende

- Modus `execute`: Aktion darf direkt ausgefuehrt werden.
- Modus `suggest`: Aktion wird nur vorgeschlagen.
- `2-Phase`: zweite Bestaetigung durch Wearer erforderlich.

## Matrix

| Action | Execute | Suggest | 2-Phase | Preconditions | Limits/Policy | Folgeaktion erlaubt | Integration |
|---|---|---|---|---|---|---|---|
| `chat_reply` | ja | ja | nein | aktive Session | KI-Charakterprofil + Session-Policy | n/a | keine |
| `hygiene_open` | ja | ja | nein | aktive Session, Oeffnung in Policy erlaubt | max. Oeffnungsdauer laut Policy | ja | optional (TTLock/chaster/emlalock je nach Setup) |
| `pause_timer` | ja | ja | nein | aktive Session | nur wenn nicht bereits pausiert; Endzeit-Korrektur erfolgt bei Resume | ja | keine |
| `unpause_timer` | ja | ja | nein | pausierte Session | Pausendauer wird auf Endzeit addiert; neue Endzeit wird fixiert | ja | keine |
| `add_time` | ja | ja | nein | aktive oder pausierte Session | Normalisierung auf `seconds`; Input: `seconds` oder `amount+unit`; erhoeht Endzeit innerhalb Policy-Grenzen | ja | keine |
| `reduce_time` | ja | ja | nein | aktive oder pausierte Session | Normalisierung auf `seconds`; Input: `seconds` oder `amount+unit`; reduziert Endzeit, aber nie unter Min-Endzeit | ja | keine |
| `update_session_settings` | ja | ja | nein | aktive oder pausierte Session | KI entscheidet autonom; nur freigegebene Felder, strikt policy-validiert; Verbot: `contract_max_end_date`, `safeword`, `traffic_light_words`, `safety_mode` | ja | optional |
| `request_control_image` | ja | ja | nein | aktive Session | Frequenz durch KI, Rahmen durch Policy | ja | keine |
| `review_control_image` | ja | ja | nein | Bild vorhanden, nicht geloescht | Kriterien aus Policy (z. B. kein Gesicht) | ja | keine |
| `ttlock_open` | ja | ja | ja | TTLock verbunden, aktive/pausierte Session | nur bei gueltiger Freigabe | ja | TTLock |
| `ttlock_close` | ja | ja | ja | TTLock verbunden, geoeffneter Zustand | nur nach Wearer-Bereitschaft | ja | TTLock |
| `chaster_sync` | ja | ja | nein | Chaster verbunden | idempotent, retry-faehig | ja | Chaster |
| `emlalock_sync` | ja | ja | nein | Emlalock verbunden | idempotent, retry-faehig | ja | Emlalock |
| `hard_stop` | ja | nein | nein | Hard-Stop in Session aktiviert | sofortige Sicherheitsroutine | nein | alle aktiven Integrationen |

## Pflicht-Auditfelder je Aktion

- `audit_id` (UUID)
- `session_id`
- `turn_id` (falls im Turn-Kontext)
- `action_type`
- `mode` (`execute`/`suggest`)
- `requested_by` (`keyholder_ai` oder `wearer`)
- `policy_snapshot_version`
- `precondition_result` (`pass`/`fail`)
- `execution_result` (`success`/`failed`/`blocked`)
- `integration_target` (optional)
- `started_at`, `finished_at`
- `error_code` (optional)
- `error_details` (optional, redacted)

## Sicherheitsregeln

- Alle externen Aktionen laufen nur ueber Action Gateway.
- `ttlock_open` und `ttlock_close` brauchen immer Wearer-Phase-2.
- Keine zusaetzliche Re-Authentifizierung fuer Phase-2 erforderlich.
- Hard-Stop setzt KI-Aktionen aus und versetzt aktive Integrationen in sicheren Zustand.

## Performance-Ziele (MVP)

- Chatpfad (`chat_reply`): priorisierte niedrige Latenz.
- Aktionspfad (Integrationen/Bildpruefung): darf hoehere Latenz haben.
- Asynchrone Verarbeitung ist fuer Integrationsaktionen zulaessig, sofern Audit und Zustandskonsistenz gewahrt bleiben.
