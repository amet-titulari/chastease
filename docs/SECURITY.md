# Security Policy – Chastease

## Ziel

Diese Datei beschreibt die aktuelle API-Sicherheitsmatrix und die wichtigsten Schutzmechanismen (Stand März 2026).

## Authentifizierung

Mehrere Schutzschichten greifen zusammen:

1. **Cookie-Auth** (`chastease_auth`, httpOnly, SameSite=Lax, optional `Secure`): Web-Routen und benutzergebundene API-Endpunkte nutzen ein Session-Cookie.
2. **Session-Ownership-Scoping**: Session-nahe API-Endpunkte prufen zusaetzlich, ob die angeforderte Session dem eingeloggten Nutzer gehoert.
3. **Admin-Session-Checks**: Admin-Oberflaechen und Admin-APIs erfordern eine eingeloggte Session mit `AuthUser.is_admin=true`.
4. **CSRF-Schutz fuer Browser-Flows**: Mutierende Browser-Requests werden per Same-Origin-Pruefung und CSRF-Header/Browser-Token abgesichert.
5. **Admin-Secret** (`CHASTEASE_ADMIN_SECRET`): Optionaler zusaetzlicher Shared-Secret-Schutz fuer besonders sensible Steuer-Endpunkte.
   - Wenn leer/nicht gesetzt: geschuetzte Endpunkte sind ohne Header erreichbar (Dev/Local-Modus).
   - Wenn gesetzt: geschuetzte Endpunkte erfordern Header `X-Admin-Secret: <value>`.
6. **Passwortspeicherung**: Neue Passwort-Hashes werden mit `pwdlib` + Argon2-Backend gespeichert; alte SHA-256-Salt-Hashes werden beim Login automatisch auf das moderne Format migriert.

Fuer besonders sensible Admin-Steuer-Endpunkte gilt bewusst ein Zwei-Layer-Modell: Admin-Session ist Pflicht, das Admin-Secret bleibt optional als zusaetzlicher Hardening-Layer. Owner-Aktionen wie Ampelstatus, Safeword oder Verifikations-Upload bleiben dagegen session-gescoped und benoetigen kein Admin-Secret.

## Endpoint-Matrix (Stand März 2026)

### Unauthentifiziert (kein Cookie noetig)

- `POST /auth/register`
- `POST /auth/login`
- `GET /` (Landingpage)
- `GET /api/health`

### Cookie-Auth + Ownership/Role-Checks

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

Hinweis: Session-bezogene Endpunkte sind auf den Session-Eigentuemer gescoped. Legacy-Sessions ohne Besitzer koennen weiterhin anonym zugreifbar sein, bis sie einem User zugeordnet sind.

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
- `POST /api/sessions/{id}/safety/traffic-light`
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

### Admin-Session erforderlich

- Persona-, Scenario-, Inventory-Posture- und grosse Teile der Games-Admin-APIs verlangen eine Admin-Session (`is_admin=true`).
- Die zugehoerigen Web-Seiten `/admin`, `/personas`, `/scenarios`, `/inventory`, `/history`, `/contracts` und Games-Admin-Oberflaechen werden ebenfalls per Admin-Session geschuetzt.

### Optional geschuetzt (bei gesetztem `CHASTEASE_ADMIN_SECRET`)

- `POST /api/sessions/{id}/chat/ws-token/rotate` (zusaetzlich immer Admin-Session erforderlich)
- `POST /api/sessions/{id}/safety/emergency-release` (zusaetzlich immer Admin-Session erforderlich)

`POST /api/sessions/{id}/verifications/{verification_id}/upload` ist bewusst **keine** Admin-Aktion, sondern eine Wearer-/Session-Aktion und bleibt owner-gescoped.

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
- Cookie-Auth plus Session-Scoping stellt sicher, dass Nutzer nicht auf fremde Sessions zugreifen koennen.
- Browser-Mutationen sollen nicht per Cross-Site-Request aus fremden Origins ausgelöst werden.
- Admin-Secret ist ein zusaetzlicher pragmatischer Mechanismus fuer besonders sensible Aktionen.

## Naechste Schritte

- Rollen- und Nutzerkonzept weiter ausbauen und Shared-Secret-Abhaengigkeit reduzieren.
- Rate-Limits fuer sensible Endpunkte.
- Optional: strengere CSRF-Policy fuer nicht-browserbasierte Mutationen.

## Betriebs-Checklist (Empfehlung)

- `CHASTEASE_ADMIN_SECRET` in produktionsnahen Setups setzen.
- `CHASTEASE_COOKIE_SECURE=true` setzen, sobald der Zugriff ueber HTTPS oder einen sicheren Reverse Proxy erfolgt.
- `CHASTEASE_SECRET_ENCRYPTION_KEY` explizit setzen, damit verschluesselte API-Keys nicht nur auf abgeleiteten Defaults beruhen.
- Secret nur ueber sichere Umgebungskonfiguration verteilen (nicht in VCS).
- Regelmaessige Rotation des Admin-Secrets einplanen.
- Reverse-Proxy/VPN-Setup so konfigurieren, dass der Server nicht direkt im Internet exponiert ist.
