# Tools

## fetch_remote_volume.py

Python replacement for the old `get.sh` script.

Features:
- Mode switch: full data or DB-only
- Automatic ZIP backup before overwrite
- SSH key compatible (`--identity-file` optional)

### Usage

```bash
python tools/fetch_remote_volume.py
```

Default behavior:
- mode: `all`
- remote docker path: `/var/lib/docker/volumes/chastease_chastease_data/_data`
- local target: `./data`
- backup target: `./backups`

### Optional arguments

```bash
python tools/fetch_remote_volume.py \
  --host 65.108.149.214 \
  --user root \
  --remote-path /var/lib/docker/volumes/chastease_chastease_data \
  --remote-data-subdir _data \
  --local-dir ./data \
  --mode all \
  --db-filename chastease.db \
  --port 22 \
  --identity-file ~/.ssh/id_ed25519 \
  --backup-dir ./backups
```

### Only fetch the database

```bash
python tools/fetch_remote_volume.py \
  --mode db-only \
  --local-dir ./data \
  --db-filename chastease.db
```

### Fetch all data

```bash
python tools/fetch_remote_volume.py --mode all --local-dir ./data
```

### Backup behavior

Before overwrite:
- `--mode all`: zips current local data directory
- `--mode db-only`: zips current local DB file

Disable backup if needed:

```bash
python tools/fetch_remote_volume.py --no-backup
```

### Dry run

```bash
python tools/fetch_remote_volume.py --dry-run
```
