# Operations – Chastease 0.5.0

Diese Betriebsnotiz friert den technischen Stand fuer `0.5.0` ein und beschreibt die Standardablaeufe fuer Upgrade, Backup/Restore, Secrets und Rollback.

## Release-Pfade

- GitHub-Repository: `git@github.com:amet-titulari/chastesae.git`
- GHCR-Image: `ghcr.io/amet-titulari/chastesae:<tag>`
- Portainer-Default: `ghcr.io/amet-titulari/chastesae:latest`

Wenn alte Referenzen wie `chastease-v3` oder `ghcr.io/amet-titulari/chastease-v3` noch in Deployments, Skripten oder Dokumentation liegen, muessen sie vor dem naechsten Rollout umgestellt werden.

## 0.5.0 Upgrade-Notizen

- Repo- und Image-Name wurden auf `chastesae` vereinheitlicht.
- Vor jedem Upgrade immer Datenbank und Medien gemeinsam sichern.
- Alembic-Stand ist fuer `0.5.0`: genau eine Initialmigration (`70237ed937a5`).
- `alembic stamp head` nur verwenden, wenn eine bestehende Datenbank bereits exakt dem aktuellen Schema entspricht und nur der Alembic-Marker fehlt.
- Leere Datenbanken koennen direkt mit `alembic upgrade head` von Grund auf neu aufgebaut werden.
- Nach dem Upgrade mindestens den manuellen Smoke-Test aus [ALPHA_READINESS.md](ALPHA_READINESS.md) durchlaufen.

## Backup

### SQLite-Datenbank

App vor dem Backup nach Moeglichkeit kurz anhalten oder Schreibtraffic minimieren.

```bash
mkdir -p backups
sqlite3 data/chastease.db ".backup 'backups/chastease-$(date +%Y%m%d-%H%M%S).db'"
```

Alternativ als einfacher Dateisnapshot:

```bash
mkdir -p backups
cp data/chastease.db "backups/chastease-$(date +%Y%m%d-%H%M%S).db"
```

### Medien

```bash
mkdir -p backups
tar -C data -czf "backups/chastease-media-$(date +%Y%m%d-%H%M%S).tar.gz" media
```

### Empfohlener Backup-Satz

- `data/chastease.db`
- `data/media/`
- optional `data/audit.log` bzw. dein konfigurierter Audit-Log-Pfad
- die produktive `.env` oder ein separates Secret-Inventory

## Restore

### Datenbank + Medien wiederherstellen

1. App/Container stoppen.
2. Aktuelle defekte Daten separat wegkopieren, nicht ueberschreiben ohne Sicherung.
3. Datenbank und Medien aus demselben Sicherungszeitpunkt zurueckspielen.
4. App starten.
5. `alembic current` und den Smoke-Test pruefen.

Beispiel:

```bash
cp backups/chastease-YYYYMMDD-HHMMSS.db data/chastease.db
tar -C data -xzf backups/chastease-media-YYYYMMDD-HHMMSS.tar.gz
alembic current
```

Wichtig: Datenbank und Medien immer paarweise aus derselben Sicherung restaurieren, damit Pfade, Verifikationsbilder und Media-Referenzen konsistent bleiben.

## Alembic-Update-Ablauf

Standardablauf fuer Upgrades:

```bash
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m pytest -q
```

Bei Container-Deployments:

```bash
docker compose pull
docker compose up -d
docker exec -it <container> alembic upgrade head
```

Wenn der Container das bei Startup bereits selbst erledigt, trotzdem danach `alembic current` und den Smoke-Test pruefen.

## Secret-Handling

Diese Werte nicht im Repo speichern und nur ueber `.env`, Secret-Store oder Portainer-Environment setzen:

- `CHASTEASE_ADMIN_SECRET`
- `CHASTEASE_AI_API_KEY`
- `CHASTEASE_WEB_PUSH_VAPID_PRIVATE_KEY`
- weitere Provider-Secrets fuer LLM, Voice oder Device-Integrationen

Regeln:

- Session-State und gespeicherte API-Keys liegen im aktuellen Alpha-Stand bewusst im Klartext in SQLite; das vereinfacht Debugging, ist aber kein akzeptabler Dauerzustand.
- At-Rest-Verschluesselung fuer diese Felder ist spaetestens vor Beta wieder einzufuehren und dann auch betriebsseitig als release-kritisch zu behandeln.
- Produktive Secrets nicht zwischen Test- und Laufzeitinstanzen teilen.
- Vor Secret-Rotation immer ein Backup erstellen und die betroffenen Integrationen danach aktiv testen.

## Rollback

Rollback ist ein kompletter Standwechsel aus Code/Image plus passendem Datenbestand.

### Minimaler Rollback-Ablauf

1. Vor dem fehlerhaften Deploy erstelltes DB-/Medien-Backup bestimmen.
2. Auf den letzten stabilen Git-Tag oder das letzte stabile GHCR-Image zurueckgehen.
3. Datenbank und Medien aus demselben Zeitpunkt wiederherstellen.
4. App starten.
5. Smoke-Test ausfuehren.

### Git-basiert

```bash
git checkout <stabiler-tag>
alembic current
```

### Container-basiert

```bash
docker pull ghcr.io/amet-titulari/chastesae:<stabiler-tag>
```

Blocker fuer Rollback:

- Datenbank bereits auf ein Schema angehoben, das der alte Code nicht versteht
- Secret-Rotation ohne Rueckwaertskompatibilitaet
- Medien oder Exporte wurden nach dem fehlerhaften Deploy veraendert, aber nicht mitgesichert

## Release-Checkliste 0.5.0

- Changelog ist eingefroren.
- `APP_VERSION` steht auf `0.5.0`.
- GHCR-/Portainer-/Repo-Pfade zeigen auf `chastesae`.
- Test-Suite ist gruen.
- `v0.5.0` ist getaggt.
- Backup/Restore-Pfad ist fuer die Zielinstanz bekannt.
- Manueller Smoke-Test wurde nach dem Deploy erfolgreich durchlaufen.
