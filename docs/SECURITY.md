# Security Policy – Chastease

## Ziel

Diese Datei beschreibt die aktuelle API-Sicherheitsmatrix im Alpha-Stand.

## Schalter

- `CHASTEASE_ADMIN_SECRET`: optionaler globaler Shared-Secret-Schutz fuer sensible Steuer-Endpunkte.
- Wenn leer/nicht gesetzt: geschuetzte Endpunkte sind ohne Header erreichbar (Dev/Local-Modus).
- Wenn gesetzt: geschuetzte Endpunkte erfordern Header `X-Admin-Secret: <value>`.

## Endpoint-Matrix (Stand Alpha)

Offen (kein `X-Admin-Secret`):

- `POST /api/sessions`
- `GET /api/sessions/{id}`
- `POST /api/sessions/{id}/sign-contract`
- `POST /api/sessions/{id}/contract/addenda`
- `POST /api/sessions/{id}/contract/addenda/{addendum_id}/consent`
- `POST /api/sessions/{id}/hygiene/openings`
- `GET /api/sessions/{id}/hygiene/openings/{opening_id}`
- `POST /api/sessions/{id}/hygiene/openings/{opening_id}/relock`
- `POST /api/sessions/{id}/safety/safeword`
- `GET /api/sessions/{id}/safety/logs`
- `POST /api/sessions/{id}/verifications/request`
- `GET /api/sessions/{id}/verifications`
- `POST /api/sessions/{id}/messages`
- `GET /api/sessions/{id}/messages`
- `POST /api/sessions/{id}/tasks`
- `GET /api/sessions/{id}/tasks`
- `POST /api/sessions/{id}/tasks/evaluate-overdue`
- `POST /api/sessions/{id}/tasks/{task_id}/status`

Optional geschuetzt (bei gesetztem `CHASTEASE_ADMIN_SECRET`):

- `POST /api/sessions/{id}/chat/ws-token/rotate`
- `POST /api/sessions/{id}/safety/traffic-light`
- `POST /api/sessions/{id}/safety/emergency-release`
- `POST /api/sessions/{id}/verifications/{verification_id}/upload`

WebSocket:

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
- Kein Ersatz fuer vollwertiges Benutzer-/Rollenmodell.
- Shared Secret ist ein pragmatischer Alpha-Mechanismus.

## Naechste Schritte

- Rollen- und Nutzerkonzept statt globalem Shared Secret.
- Rate-Limits und Audit-Trails fuer sensible Endpunkte.
- Optional: Ende-zu-Ende Session-Binding fuer Browser-Clients.

## Betriebs-Checklist (Empfehlung)

- `CHASTEASE_ADMIN_SECRET` in produktionsnahen Setups setzen.
- Secret nur ueber sichere Umgebungskonfiguration verteilen (nicht in VCS).
- Regelmaessige Rotation des Admin-Secrets einplanen.
- Reverse-Proxy/VPN-Setup so konfigurieren, dass der Server nicht direkt im Internet exponiert ist.
