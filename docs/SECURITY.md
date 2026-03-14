# Security Policy – Chastease

## Ziel

Diese Datei beschreibt die aktuelle API-Sicherheitsmatrix (Stand v0.2.1).

## Authentifizierung

Zwei Schutzstufen:

1. **Cookie-Auth** (`access_token`, httpOnly, SameSite=Lax): Alle Web-Routen und die meisten API-Endpunkte erfordern einen gueltigen Login-Cookie. Registrierung und Login sind unauthentifiziert.
2. **Admin-Secret** (`CHASTEASE_ADMIN_SECRET`): Optionaler zusaetzlicher Shared-Secret-Schutz fuer besonders sensible Steuer-Endpunkte.
   - Wenn leer/nicht gesetzt: geschuetzte Endpunkte sind ohne Header erreichbar (Dev/Local-Modus).
   - Wenn gesetzt: geschuetzte Endpunkte erfordern Header `X-Admin-Secret: <value>`.

## Endpoint-Matrix (Stand v0.2.1)

### Unauthentifiziert (kein Cookie noetig)

- `POST /auth/register`
- `POST /auth/login`
- `GET /` (Landingpage)
- `GET /api/health`

### Cookie-Auth (Login erforderlich)

**Sessions:**
- `POST /api/sessions`
- `GET /api/sessions/{id}`
- `PUT /api/sessions/{id}/player-profile`
- `GET /api/sessions/{id}/seal-history`
- `GET /api/sessions/{id}/events`
- `GET /api/sessions/{id}/events/export`
- `GET /api/sessions/{id}/export`
- `GET /api/sessions/{id}/contract`
- `GET /api/sessions/{id}/contract/export`
- `POST /api/sessions/{id}/sign-contract`
- `POST /api/sessions/{id}/contract/addenda`
- `POST /api/sessions/{id}/contract/addenda/{addendum_id}/consent`
- `GET /api/sessions/blueprints/completed`
- `GET /api/sessions/blueprints/{id}`

**Timer:**
- `GET /api/sessions/{id}/timer`
- `POST /api/sessions/{id}/timer/add`
- `POST /api/sessions/{id}/timer/remove`
- `POST /api/sessions/{id}/timer/freeze`
- `POST /api/sessions/{id}/timer/unfreeze`

**Chat:**
- `POST /api/sessions/{id}/messages`
- `GET /api/sessions/{id}/messages`
- `POST /api/sessions/{id}/messages/media`
- `POST /api/sessions/{id}/messages/image`
- `POST /api/sessions/{id}/messages/regenerate`

**Tasks:**
- `POST /api/sessions/{id}/tasks`
- `GET /api/sessions/{id}/tasks`
- `POST /api/sessions/{id}/tasks/evaluate-overdue`
- `POST /api/sessions/{id}/tasks/{task_id}/status`

**Hygiene:**
- `GET /api/sessions/{id}/hygiene/quota`
- `POST /api/sessions/{id}/hygiene/openings`
- `GET /api/sessions/{id}/hygiene/openings/{opening_id}`
- `POST /api/sessions/{id}/hygiene/openings/{opening_id}/relock`

**Safety:**
- `POST /api/sessions/{id}/safety/safeword`
- `POST /api/sessions/{id}/safety/resume`
- `GET /api/sessions/{id}/safety/logs`

**Verification:**
- `POST /api/sessions/{id}/verifications/request`
- `GET /api/sessions/{id}/verifications`

**Push Notifications:**
- `GET /api/push/config`
- `GET /api/sessions/{id}/push/subscriptions`
- `POST /api/sessions/{id}/push/subscriptions`
- `DELETE /api/sessions/{id}/push/subscriptions/{subscription_id}`
- `POST /api/sessions/{id}/push/test`

**Personas:**
- `GET /api/personas`
- `POST /api/personas`
- `GET /api/personas/{id}`
- `PUT /api/personas/{id}`
- `DELETE /api/personas/{id}`
- `GET /api/personas/presets`
- `GET /api/personas/scenario-presets`
- `GET /api/personas/card-schema`
- `POST /api/personas/map-card`
- `GET /api/personas/{id}/export`
- `GET /api/personas/export`
- `POST /api/personas/import`

**Scenarios:**
- `GET /api/scenarios`
- `POST /api/scenarios`
- `GET /api/scenarios/{id}`
- `PUT /api/scenarios/{id}`
- `DELETE /api/scenarios/{id}`
- `GET /api/scenarios/presets`
- `GET /api/scenarios/{id}/export`
- `POST /api/scenarios/import`

**Inventory:**
- `GET /api/inventory/items`
- `POST /api/inventory/items`
- `PUT /api/inventory/items/{item_id}`
- `DELETE /api/inventory/items/{item_id}`
- `GET /api/inventory/items/{item_id}/export`
- `GET /api/inventory/items/export`
- `POST /api/inventory/items/import`
- `GET /api/inventory/scenarios/{scenario_id}/items`
- `PUT /api/inventory/scenarios/{scenario_id}/items`
- `GET /api/inventory/sessions/{session_id}/items`
- `POST /api/inventory/sessions/{session_id}/items`
- `PUT /api/inventory/sessions/{session_id}/items/{session_item_id}`
- `DELETE /api/inventory/sessions/{session_id}/items/{session_item_id}`

**Media:**
- `POST /api/media/avatar`
- `GET /api/media/{media_id}`
- `PUT /api/media/{media_id}`
- `GET /api/media/{media_id}/content`
- `DELETE /api/media/{media_id}`

**Voice:**
- `GET /api/voice/realtime/{session_id}/status`
- `POST /api/voice/realtime/{session_id}/client-secret`
- `POST /api/voice/tts`

**Settings / Experience:**
- `GET /api/settings/summary`
- `POST /api/settings/llm`
- `POST /api/experience/draft`
- `POST /api/llm/test`

**Web-Seiten (Cookie-Auth):**
- `GET /setup`, `POST /setup/complete`, `POST /setup/test-llm`
- `GET /profile`, `POST /profile/llm`, `POST /profile/llm/test`, `GET /profile/llm/status`
- `POST /profile/setup`, `POST /profile/audio`, `POST /profile/audio/test`, `POST /profile/restart-setup`
- `GET /experience`, `GET /play/{session_id}`
- `GET /history`, `GET /contracts`, `GET /contract/{session_id}`
- `GET /personas`, `GET /scenarios`, `GET /inventory`
- `GET /testconsole`
- `POST /auth/logout`

### Optional geschuetzt (bei gesetztem `CHASTEASE_ADMIN_SECRET`)

- `POST /api/sessions/{id}/chat/ws-token/rotate`
- `POST /api/sessions/{id}/safety/traffic-light`
- `POST /api/sessions/{id}/safety/emergency-release`
- `POST /api/sessions/{id}/verifications/{verification_id}/upload`

### WebSocket

- `ws /api/sessions/{id}/chat/ws?token=<ws_auth_token>`
  - `ws_auth_token` wird in Session-Responses bereitgestellt.
  - Token-Rotation invalidiert bestehende WS-Verbindungen serverseitig.

## Fehlerformat und Nachvollziehbarkeit

- API-Fehler verwenden ein einheitliches JSON-Format:
	- `request_id`
	- `error.code`
	- `error.message`
	- optional `error.details`
- `request_id` erleichtert Korrelation zwischen Client-Fehlern und Server-Logs.

## Bedrohungsmodell (Kurz)

- Fokus: Schutz vor unbeabsichtigter/unerwuenschter Steuerung durch fremde Clients im lokalen Netz.
- Cookie-Auth stellt sicher, dass nur eingeloggte Benutzer auf Session-Daten zugreifen koennen.
- Admin-Secret ist ein zusaetzlicher pragmatischer Mechanismus fuer besonders sensible Aktionen.

## Naechste Schritte

- Rollen- und Nutzerkonzept (Multi-User) statt globalem Shared Secret.
- Rate-Limits fuer sensible Endpunkte.
- Optional: Ende-zu-Ende Session-Binding fuer Browser-Clients.

## Betriebs-Checklist (Empfehlung)

- `CHASTEASE_ADMIN_SECRET` in produktionsnahen Setups setzen.
- Secret nur ueber sichere Umgebungskonfiguration verteilen (nicht in VCS).
- Regelmaessige Rotation des Admin-Secrets einplanen.
- Reverse-Proxy/VPN-Setup so konfigurieren, dass der Server nicht direkt im Internet exponiert ist.
