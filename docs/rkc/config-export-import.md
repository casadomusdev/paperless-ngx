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
| Groups | Groups with their Django permissions (members are **not** transferred) |
| Content | Correspondents, Tags (incl. hierarchy), Document Types, Storage Paths, Custom Fields |
| Saved views | Saved Views and their filter rules |
| Workflows | Workflows, triggers, actions, email actions, webhook actions |
| Mail | Mail accounts, mail rules |
| UI "Settings" page | `UiSettings`, including default permissions |
| UI "Configuration" page | `ApplicationConfiguration` (incl. global saved-view ordering, app title and logo) |

### Deliberately excluded (per-instance)

Users and SSO apps/tokens are **not** exported. Anything they own or reference is
handled as follows:

- Object ownership (`owner`) is exported as a **username** and re-resolved on
  the target. If the username does not exist there, the object becomes
  ownerless (which, in this fork, means visible and editable by all users).
  `--owner USERNAME` forces a single owner for everything.
- Default permissions in `UiSettings` are remapped by username and group name;
  references that cannot be resolved are dropped.
- Saved-view filter rules that reference users (owner rules) are dropped.
- Group **members** are not transferred — groups arrive without users. Their
  Django permissions **are** transferred, matched by
  `(app_label, model, codename)` so they map onto the target's own permission
  rows. Importing a group replaces its permission set with the exported one.

## Path resolution

Relative paths are resolved against the **current working directory**. In Docker
the management-command wrappers `cd` into `${PAPERLESS_SRC_DIR}`
(`/usr/src/paperless/src`) before running Django — so a relative path is taken
relative to *that* directory, not to the folder your shell was in. Use the
container's `../export` mount:

```bash
docker compose exec webserver config_exporter ../export --zip
docker compose exec webserver config_importer ../export/config-export-2026-10-13.zip
```

When a path does not exist the command reports the resolved absolute path and
the current working directory, which makes this immediate to spot.

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
| `--keep-enabled` | Keep workflows and mail rules in their exported enabled state (default: both are imported **disabled**) |
| `--no-preserve-ids` | Let the database assign new primary keys instead of reusing the exported ids |
| `--clear` | Delete existing configuration objects first so the target matches the export exactly (see below) |
| `--no-progress-bar` | Suppress progress output |

### Merge semantics

The importer is **idempotent** and works against an empty *or* populated
instance:

- Records with a name (groups, tags, document types, storage paths,
  correspondents, custom fields, mail accounts, mail rules, saved views,
  workflows) are matched by name and **updated in place** if they already exist,
  otherwise created.
- Groups are matched by name; their Django permissions are replaced with the
  exported set (members are left untouched).
- **Workflows and mail rules are imported disabled** so they cannot start firing
  or fetching mail before an admin has reviewed them. Pass `--keep-enabled` to
  preserve the enabled state recorded in the export.
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

### Clearing the target first (`--clear`)

A plain import is a **merge** — objects that exist on the target but are absent
from the export stay behind, and objects present in both are merged by name. If
you want the target to match the export exactly (for example after a few
experimental imports left duplicates behind, or to get the original ids back),
import with `--clear`:

```bash
docker compose exec webserver config_importer ../export/config-export-2026-10-14.zip --clear
```

`--clear` deletes the target's tags, document types, correspondents, storage
paths, custom fields, saved views, workflows, mail accounts, mail rules and
groups *before* importing, using Django's ORM (so cascades, join tables and
denormalised columns stay consistent) plus the guardian object-permission rows
for those models. It runs **inside the same transaction as the import**, so a
failure — or `--dry-run` — leaves the instance untouched.

Two caveats, both consequences of paperless's data model:

- **Tags are detached from documents.** Deleting a tag removes it from every
  document that used it. On an instance that already holds documents, that
  tagging information cannot be restored by the import.
- **Group memberships are lost.** Users are never imported (they are
  per-instance), so groups are re-created empty.

`UiSettings` (per-user preferences, incl. default permissions) and the
`ApplicationConfiguration` singleton are deliberately **not** cleared — the
import overwrites them anyway.

### Id preservation

External tooling addresses paperless objects by id — for example
`AI_OCR_TAG_ID`, `PAPERLESS_CONSUMER_READD_TAG_ID`,
`PAPERLESS_MAIL_SEND_SUCCESS_TAG_ID` and the scripts in `scripts/`. To keep those
working after a migration, **newly created rows reuse the id from the export**
wherever that id is still free. Database sequences are realigned afterwards so
later inserts cannot collide with a reused id.

Rules and limits:

- Ids are only reused for rows that are **created**. If an object with the same
  name already exists on the target it is merged into, keeping *its* existing id.
- If the exported id is already taken by a different object, a warning is printed
  and a new id is assigned for that record.
- `--no-preserve-ids` disables the behaviour and lets the database assign ids.
- Saved-view filter rules and workflow triggers/actions also keep their ids;
  `ApplicationConfiguration` is the singleton with id `1` either way.

Consequently, to reproduce the source ids exactly you need a target where those
ids are free. Use `--clear` (below) to remove the target's existing configuration
in the same transaction, then everything is created fresh with the exported ids.

To see the mapping between names and current ids, e.g.:

```shell
docker compose exec webserver python3 manage.py shell -c \
  "from documents.models import Tag; print(list(Tag.objects.values_list('name','id')))"
```

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
  the export are left untouched unless `--clear` is given.
- References to **users that do not exist on the target** are dropped with a
  warning — users are never imported. This means `owner`, `assign_owner`,
  `assign_view_users`, `assign_change_users`, `default_*_users` and saved-view
  owner rules end up empty rather than blocking the import. Group references
  resolve, because groups *are* imported.
- Imported workflows and mail rules arrive **disabled** by design (see merge
  semantics); re-enable them deliberately once you have reviewed them, or use
  `--keep-enabled` if the export's state should be trusted verbatim.
- Encrypted mail secrets require the export passphrase; there is no key escrow.
- Because users are per-instance, personal saved views and per-user UI settings
  only transfer to a target user with the **same username** (override with
  `--ui-settings-user`).