# Alpha Readiness – Chastease

Dieses Dokument definiert, wann `0.5.0` als abgeschlossen gilt und unter welchen Bedingungen ein erster Alpha-Zyklus gestartet werden kann.

## Alpha-Ziel

Alpha bedeutet fuer Chastease:

- Feature-Umfang fuer den Solo-Betrieb ist breit genug.
- Kernfluesse sind technisch stabil und dokumentiert.
- Bekannte Maengel sind bewusst akzeptiert und keine versteckten Release-Blocker.
- Deploy-/Rollback-/Smoke-Prozess ist reproduzierbar.

## Was fuer Alpha akzeptabel ist

- UI-Polish-Luecken ohne funktionalen Schaden.
- Unvollstaendige Detaildokumentation in Randbereichen.
- Nicht-kritische Performance-Themen bei grossen Historien oder Medienmengen.
- Begrenzte In-Memory-Rate-Limits statt vollstaendig verteilter Abuse-Protection.
- Noch nicht finalisierte Komfortfunktionen fuer Remote-Keyholder, Gamification oder weitere Integrationen.
- Device-/Toy-Integrationen, die optional bleiben und bei Ausfall nicht den Session-Kernfluss blockieren.

## Was fuer Alpha ein Blocker ist

- Crash oder Datenverlust in Session-Start, Vertrag, Chat, Task, Verification, Safety oder Export.
- Fehlerhafte Rollenzuordnung bei admin-geschuetzten Endpunkten.
- Nicht reproduzierbarer Upgrade- oder Rollback-Pfad.
- Gruene lokale Test-Suite fehlt.
- Veraltete Repo-/Image-Pfade fuehren auf falsche Artefakte.
- Sicherheitskritische Fluesse sind nur mit stillen Fehlern oder unklarer Fehlermeldung bedienbar.
- Safety-Abbruch funktioniert nicht sofort oder hinterlaesst inkonsistenten Session-Status.

## Exit-Kriterien fuer 0.5.0

- `APP_VERSION` ist `0.5.0`.
- Changelog und Upgrade-Notizen sind eingefroren.
- Betriebsnotizen fuer Backup/Restore, Secrets und Rollback sind dokumentiert.
- GitHub-/GHCR-/Deploy-Referenzen sind konsistent.
- CI laeuft automatisiert.
- `python -m pytest -q` ist gruen.
- Manueller Smoke-Test ist erfolgreich.

## Manueller Smoke-Test

Vor jedem Alpha-Deploy die folgenden Punkte einmal vollstaendig durchgehen.

### 1. Setup / Login

1. Landing aufrufen.
2. Registrieren oder mit Testaccount einloggen.
3. Experience-/Dashboard-Aufruf pruefen.

Erwartung:

- Login klappt.
- Keine Redirect-Schleifen.
- Dashboard und Chat sind erreichbar.

### 2. Session-Start / Vertrag

1. Neue Session anlegen.
2. Persona, Dauer und Vertragsrahmen setzen.
3. Vertrag anzeigen und signieren.

Erwartung:

- Session wird erstellt.
- Vertrag ist sichtbar.
- Nach Signatur ist die Session `active`.

### 3. Chat

1. Eine normale Nachricht senden.
2. Antwort im Chat pruefen.

Erwartung:

- Antwort kommt ohne 500er.
- Chat-Historie bleibt lesbar.

### 4. Task

1. Im Chat explizit um eine Aufgabe bitten.
2. Offene Tasks im Chat oder Dropdown pruefen.

Erwartung:

- Es entsteht mindestens eine Aufgabe.
- Deadline und Status werden sauber angezeigt.

### 5. Verification

1. Task mit Fotoverifikation oder manuelle Verifikationsanfrage starten.
2. Bild hochladen.

Erwartung:

- Upload funktioniert.
- Status wird auf `confirmed` oder `suspicious` gesetzt.
- Kein Serverfehler bei standalone oder verknuepfter Verifikation.

### 6. Safety

1. Ampel auf Gelb oder Rot pruefen.
2. Danach Safeword ausloesen.

Erwartung:

- Safety-Status wird sofort uebernommen.
- Session landet nach Safeword in `safeword_stopped`.
- Folgende Chat-Antworten bleiben im Safety-Kontext.

### 7. Export

1. Contract-Export pruefen.
2. Event- oder Session-Export pruefen.

Erwartung:

- Export-Endpunkte liefern 200.
- Inhalte sind nicht leer.

### 8. Push

1. Test-Subscription anlegen.
2. Push-Test ausloesen.

Erwartung:

- Endpoint antwortet erfolgreich.
- Bei fehlender Produktivkonfiguration kommt eine saubere, nicht-crashende Rueckmeldung.

## Empfohlener Start fuer die Alpha-Phase

- Release `0.5.0` als eingefrorene Basis behandeln.
- Danach Stabilisierung und Qualitaet unter `0.6.0-alpha.x` weiterziehen.
- Neue Features nur aufnehmen, wenn sie keinen Kernfluss destabilisieren.
