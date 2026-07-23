# Backup Subsystem Design

`vpemaster` backups are CLI-driven (no web UI). All supported
operations live under `flask resources` (`app/commands/backup.py`) and
delegate to `app/services/backup_service.py`.

## Scope

Backup resources, each stored under `instance/backup/<resource>/`:

| Resource | Source | Format |
|---|---|---|
| `db` | MySQL via `mysqldump` | plain SQL — always **full** |
| `system` | `static/images`, `static/avatars` | zip |
| `club` | `static/club_resources` | zip |
| `all` | union of the above | mixed |

`static/uploads` is covered only by the legacy `flask pack`/`unpack`
flow, which is separate from this subsystem and not managed by rotation.

## Filename contract (the parsing contract)

Backups are identified purely by filename — there is no manifesto or
sidecar metadata. `get_backups_sorted` parses type and timestamp from
the filename with these regexes:

- DB:  `backup_db_full_(\d{8})_(\d{6})\.sql`
- Files: `backup_<resource>_(full|inc|diff)_(\d{8})_(\d{6})\.zip`

Any new backup type needs a token added to the regex in
`get_backups_sorted` and a matching branch in `restore_file_backup`
and `_rotate_backups`.

## Strategies (file resources only)

| Strategy | Token | Baseline | Restore chain | Storage cost | Restore cost |
|---|---|---|---|---|---|
| Full | `full` | none | single zip | highest | lowest |
| Incremental | `inc` | latest backup of any type | parent_full + every backup up to target | lowest | highest (replay all) |
| Differential | `diff` | latest **full** backup | parent_full + target diff only | medium (grows over time) | low (2 zips) |
| Auto | (resolves to `inc` or `full`) | — | — | — | — |

`auto` (the CLI default when no strategy flag is given) is incremental if
a prior full backup exists for the resource, otherwise it takes a full
backup. This lets the caller stay strategy-agnostic — the first run
seeds a full, every subsequent run adds a small incremental.

Differential backups trade storage for restore simplicity. Restore
applies at most 2 zips; if a full chain is corrupted or rotated away, a
diff still restores cleanly as long as the parent full survives.

DB has no incremental/differential story — it is always a full
`mysqldump`.

### Baseline semantics (invariant)

- `inc` baseline = `max(timestamp)` of all backups for the resource
  (full or inc).
- `diff` baseline = `max(timestamp)` of all **full** backups for the
  resource (a `diff` never builds on top of another diff or inc).

This is the difference between the two strategies. **Do not collapse
them.** If you ever need "delta since the last diff", that is a third
distinct strategy and needs a new token.

### Fallback when no baseline exists

- `increment` with no prior backups → silently runs a **full** backup.
- `differential` with no prior **full** backup → silently runs a **full**
  backup.
- A differential is *not* valid without a parent full. Restore will
  error out if the parent full has been deleted or rotated away.

## Change detection

Changes are detected by file **mtime** (truncated to seconds), strictly
greater than the baseline timestamp. No content hashing — a touched
file with identical content is re-backed-up.

Implications, all known and accepted:

- Clock skew can cause missed or duplicate captures. Production backups
  run on a single host; this is not a concern in practice.
- After `flask sync` pulls remote backups via `rsync -a`, remote mtimes
  are preserved on disk — subsequent incremental/differential backups
  work correctly.
- After a restore, `shutil.unpack_archive` resets the extracted files'
  mtimes to "now". If you take an incremental immediately after
  restoring onto a dirty tree, the restored files will appear "changed"
  again. Restores should be performed on a clean tree (or into a fresh
  checkout) to avoid this drift.

## Deletion tracking

None. Neither `inc` nor `diff` zips record deletions on the source.
Restoring onto a non-empty target leaves stale files behind. Clean the
target directory (or restore into a fresh checkout) if you need an
exact mirror.

## Rotation (`_rotate_backups`)

- Keeps the 5 most recent **full** backups; older fulls are deleted.
- When a full is deleted, every `inc` and `diff` whose timestamp falls
  in `[full_time, next_full_time)` is deleted with it.
- Rotation runs **only after a successful full backup**. Incremental
  and differential backups do not trigger rotation (they would risk
  orphaning themselves by deleting their own parent full).
- The retention count (`5`) is currently hardcoded.

## Restore (`restore_file_backup`)

- Picks a target by `--file` or `--latest`.
- `full` → single `shutil.unpack_archive` into `current_app.root_path`.
- `inc` → find nearest preceding `full`, replay `[full] + every backup
  in (full, target]` in order. Later zips overwrite earlier-extracted
  files.
- `diff` → find nearest preceding `full`, apply `[full, target_diff]`
  only — the diff is a complete delta against the full, no intermediate
  backups needed.
- If a target file isn't in `get_backups_sorted` (e.g. unknown
  filename) but exists on disk, it falls back to a direct unpack as a
  best-effort full restore.

## CLI

```
flask resources [-t <type>] backup [--full | --increment | --differential | --diff]
flask resources [-t <type>] restore [--latest | --file <path>] [--no-upgrade] [--stamp <ver>]
```

- `--full`, `--increment`, `--differential`/`--diff` are mutually
  exclusive. If none is given, `auto` is the default — incremental if a
  prior full backup exists for the resource, otherwise full.
- For `restore`, if no `--file`, `--latest`, or `--*-file` is given, the
  latest backup of each selected resource is restored (the same `auto`
  default as `backup`). `flask resources restore` with no args restores
  the latest db + system + club in one shot.
- `db` ignores strategy flags — DB is always full.
- `--differential` and `--diff` are aliases for the same flag.

## Cron (`scripts/setup_cron_backups.sh`)

Production cron currently only does `--full` (Wed) and daily DB backups.
Incremental and differential are opt-in via the CLI; not enabled in
cron. Differential is a good candidate for nightly file backups in a
future cron update (smaller than a nightly full, simpler restore than
incremental) — but that decision is configuration, not code.

## Remote sync (`flask sync`, `sync_remote_backup`)

Pull-only via `rsync -avz --delete`. The local mirror is an exact copy
of remote, so rotation and restore work identically on the synced copy.
Because `--delete` prunes local extras, do not run differential backups
on the local mirror between syncs; the next sync will rearrange or
delete files and confuse any local rotation state.