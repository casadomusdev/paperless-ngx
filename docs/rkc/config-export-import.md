# Configuration Export / Import

Move **all** paperless-ngx configuration — without documents — from one instance
to another, including between instances that already contain data.

Implemented as two management commands (`config_exporter`, `config_importer`)
backed by `documents/config_exchange/`.

## What is exported

Everything a superuser can configure. Documents, notes, share links, tasks,
workflow runs, processed mail and pending emails are **never** exported.

| Area | Models |
|------|--------|
| Content | Correspondents, Tags (incl. hierarchy), Document Types, Storage Paths, Custom Fields |
| Saved views | Saved Views and their filter rules |
| Workflows | Workflows, triggers, actions, email actions, webhook actions |
| Mail | Mail accounts, mail rules |
| UI "Settings" page | `UiSettings`, including default permissions |
| UI "Configuration" page | `ApplicationConfiguration` (incl. global saved-view ordering, app title and logo) |

### Deliberately excluded (per-instance)

Users, groups, permissions and SSO apps/tokens are **not** exported. Anything
they own or reference is handled as follows:

- Object ownership (`owner`) is exported as a **username** and re-resolved on
  the target. If the username does not exist there, the object becomes
  ownerless (which, in this fork, means visible and editable by all users).
  `--owner USERNAME` forces a single owner for everything.
- Default permissions in `UiSettings` are remapped by username/group name;
  references that cannot be resolved are dropped.
- Saved-view filter rules that reference users (owner rules) are dropped.

## Exporting

```bash
# Docker
docker compose exec webserver config_exporter ../export
docker compose exec webserver config_exporter ../export --zip --passphrase "secret"

# Bare metal
cd /path/to/paperless/src
python3 manage.py config_exporter /path/to/export
```

| Option | Description |
|--------|-------------|
| `target` | Directory to write the export into |
| `-z`, `--zip` | Write a single zip file into the target directory |
| `-zn`, `--zip-name` | Zip filename (without extension) |
| `--passphrase` | Encrypt mail passwords/refresh tokens with this passphrase |
| `--no-progress-bar` | Suppress progress output |

The export directory contains `config.json` (records + cross-references),
`metadata.json` (version and, if used, the encryption parameters) and an
`assets/` folder holding the application logo when one is configured.

> **Secret handling.** Without `--passphrase`, mail account passwords and
> refresh tokens are written in plaintext. If a passphrase was used, the same
> passphrase must be supplied to the importer.

## Importing

```bash
# Docker
docker compose exec webserver config_importer ../export
docker compose exec webserver config_importer ../export --dry-run

# Bare metal
python3 manage.py config_importer /path/to/export
```

| Option | Description |
|--------|-------------|
| `source` | Directory or `.zip` produced by `config_exporter` |
| `--passphrase` | Passphrase used to encrypt the export |
| `--owner USERNAME` | Force all imported objects to be owned by this user |
| `--ui-settings-user USERNAME` | Apply imported UI settings to this user (default: match by username) |
| `--dry-run` | Validate and report, then roll back everything |
| `--no-progress-bar` | Suppress progress output |

### Merge semantics

The importer is **idempotent** and works against an empty *or* populated
instance:

- Records with a name (tags, document types, storage paths, correspondents,
  custom fields, mail accounts, mail rules, saved views, workflows) are matched
  by name and **updated in place** if they already exist, otherwise created.
- Workflow triggers/actions have no natural name and are matched by their full
  field signature: an identical row is reused, otherwise a new one is created.
- Saved-view filter rules are replaced wholesale for every saved view present
  in the export.
- `ApplicationConfiguration` is a singleton and is always overwritten.
- Every foreign key, many-to-many relation and embedded id (filter-rule values,
  workflow custom-field queries, `assign_custom_fields_values`, global saved-view
  ordering) is remapped from source to target.

Records whose **required** foreign keys cannot be resolved are skipped with a
warning; individual unresolvable references are dropped.

Running the same import twice causes no duplicates.

## Examples

Mirror the configuration of a production instance into a staging instance:

```bash
# On production
docker compose exec webserver config_exporter ../export --zip

# Copy export-<date>.zip to staging, then
docker compose exec webserver config_importer ../export/export-2024-01-01.zip
```

Pre-flight a change without touching the target:

```bash
docker compose exec webserver config_importer ../export --dry-run
```

## Notes and limitations

- Import is a merge, not a mirror: objects that exist on the target but not in
  the export are left untouched. A destructive "replace" mode does not exist.
- Encrypted mail secrets require the export passphrase; there is no key escrow.
- Because users are per-instance, personal saved views and per-user UI settings
  only transfer to a target user with the **same username** (override with
  `--ui-settings-user`).