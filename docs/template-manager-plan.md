# Template Manager — Implementation Plan

## Context

vpemaster stores meeting templates as CSV files on disk, scoped per club at
`app/static/club_resources/<club_id>/templates/*.csv`. Today the only ways to
manage them are an `#export-template-btn` on the agenda page (creates a new
template from a meeting's `SessionLog` rows) and a JS-driven delete — there is
no list, no load, no upload, no in-place editor, and no UI for users with
`MEETING_MANAGE` to maintain their club's templates. There is also a hardcoded
fallback dict in `Meeting.get_type_to_template` that duplicates the file-
listing logic, two out-of-sync seed locations, and per-call nested helpers in
`_generate_logs_from_template`.

This change adds a Template Manager (a new submenu item under the Meetings
dropdown, gated by `MEETING_MANAGE`) that lets club users list, open-in-editor,
delete, copy-from-seed, and export-from-meeting for the current club's
templates. The existing `#export-template-btn` is removed and its code moves
into the new manager. Per-club scoping is preserved throughout — every
operation only touches the current club's directory.

## Design summary

- New service `app/services/meeting_template_service.py` becomes the single
  source of truth for template I/O, validation, sanitization, and atomic
  writes.
- New blueprint `app/template_manager_routes.py` registered at
  `/meetings/templates/...`, gated by `@club_permission_required('MEETING_MANAGE')`.
- Two new Jinja pages (`list.html`, `editor.html`) and one JS file
  (`template_manager.js`) drive the UI.
- `_generate_logs_from_template` is slimmed to use the new service for CSV
  parsing; the meeting-creation business logic stays in `agenda_routes.py`.
- One-time seed consolidation: copy 6 CSVs from `app/static/mtg_templates/`
  into `app/static/club_resources/0/templates/`, then delete
  `app/static/mtg_templates/`.

## Per-club scoping (reinforced)

Every operation is scoped to `session['current_club_id']` resolved by
`get_current_club_id()` (`app/club_context.py:6-16`). "Copy from global seed"
copies from `club_resources/0/templates/` (club id 0) into the *current*
club's directory — it does not write to club 0. SysAdmins manage a different
club by switching clubs via the existing club switcher; no new global view is
added.

## New files

| Path | Purpose |
| --- | --- |
| `app/services/meeting_template_service.py` | Single source of truth for template I/O, validation, sanitization, atomic writes, seed listing |
| `app/template_manager_routes.py` | Blueprint `template_bp` registered at `/meetings/templates` |
| `app/templates/template_manager/list.html` | Index page listing the club's templates with create-from-seed, export-from-meeting, edit, delete actions |
| `app/templates/template_manager/editor.html` | Inline table editor with Type dropdown, Move Up/Down, Add Row, Delete Row, Save |
| `app/static/js/template_manager.js` | Editor state and row ops; sends the full ordered list on Save |
| `app/static/css/template_manager.css` | Editor table styling (only what isn't in `agenda.css`) |

Register the blueprint in `app/__init__.py` next to `agenda_bp`.

## Routes (`app/template_manager_routes.py`)

All routes use `@login_required` → `@authorized_club_required` →
`@club_permission_required(Permissions.MEETING_MANAGE)`. The last decorator
already calls `abort(403)` per `app/auth/utils.py:76`.

| Method + URL | Returns | Notes |
| --- | --- | --- |
| `GET /meetings/templates` | `list.html` | Lists the current club's CSVs: `(name, row_count, mtime)` |
| `GET /meetings/templates/new?seed=<name>` | redirect to editor | Copies `club_resources/0/templates/<name>.csv` into the club dir |
| `POST /meetings/templates/export` | redirect to editor | Body: `{meeting_id, template_name}`; reuses the writer logic from `agenda_routes.py:1276-1298` |
| `GET /meetings/templates/edit/<path:name>` | `editor.html` with parsed rows | `name` is the `.csv` filename |
| `POST /meetings/templates/edit/<path:name>` | redirect to list on success; re-render on failure | Body: ordered list of row dicts |
| `POST /meetings/templates/delete` | JSON | Body: `{name}`; uses `os.path.commonpath` (not `startswith`) for traversal safety |

## Service — `app/services/meeting_template_service.py`

Module-level constants and exceptions at top:

```
TEMPLATES_SUBDIR = 'templates'
CSV_HEADER = ['Type','Title','Role','Owner','Duration_Min','Duration_Max','Hidden']

class TemplateError(Exception): ...
class TemplateNotFound(TemplateError): ...
class TemplateNameInvalid(TemplateError): ...
class TemplatePathEscape(TemplateError): ...
```

Functions:

- `_club_dir(club_id) -> str` — `static/club_resources/<id>/templates`, makedirs
- `_seed_dir() -> str` — `static/club_resources/0/templates`
- `_safe_join(club_id, filename) -> str` — raises `TemplateNameInvalid` / `TemplatePathEscape`; uses `os.path.commonpath` to defeat the `/1x/` bypass that the current `startswith` check at `agenda_routes.py:1337` allows
- `sanitize_filename(name: str) -> str` — strip, replace spaces with `_`, reject `/`, `\`, `..`, leading `.`, empty
- `list_templates(club_id) -> [{filename, display_name, row_count, mtime}]`
- `get_template(club_id, filename) -> {header, rows}` — catches `csv.Error`, returns empty rows on malformed input, logs a warning
- `create_from_seed(club_id, seed_filename, new_name) -> filename` — copies from club 0
- `create_from_meeting(club_id, meeting_id, new_name) -> filename` — moves the writer logic out of `agenda_routes.py:1276-1298`
- `save_template(club_id, filename, rows) -> None` — writes to `<file>.tmp` then `os.replace` (atomic)
- `delete_template(club_id, filename) -> None`
- `list_seed_templates() -> [name]`
- `parse_template_rows(club_id, filename) -> List[Dict]` — inverse of writer; used by `_generate_logs_from_template` to keep meeting-creation logic in `agenda_routes.py`

Header validation: read first row, compare to `CSV_HEADER`; if missing required
columns, return `{header: CSV_HEADER, rows: []}` and log a warning. Skip empty
lines. Never let a malformed CSV crash the page.

## Editor page (`editor.html`) — columns and actions

Columns (matching the CSV):

1. **No.** — read-only display
2. **Type** — `<select>` with `Section`, `Generic`, plus the club's session types from `SessionType.get_all_for_club(club_id)`
3. **Title** — text input
4. **Role** — free-text input (v1; auto-resolve via `datalist` is a v2)
5. **Owner** — free-text input (v1; same)
6. **Min** — number input
7. **Max** — number input (empty allowed)
8. **Hidden** — checkbox
9. **Actions** — Up, Down, Delete

Form fields outside the table: template name (read-only, shown as
`<filename>.csv`), CSRF token, Save, Cancel.

The `Role`/`Owner` autocomplete is deferred to v2 — the existing
`_generate_logs_from_template` already resolves free-text owner names against
the contact table, so v1 behaviour matches today.

## JS (`app/static/js/template_manager.js`)

State: `let rows = []`. Render rebuilds `<tbody>` on every mutation. Save:
serializes to JSON, `fetch(POST /meetings/templates/edit/<name>)`, on success
`location.assign('/meetings/templates')`. Helpers: `addRow()`, `moveRow(idx,
dir)`, `deleteRow(idx)`, `collectRows()`, `render()`.

The list page posts to four endpoints: copy-from-seed (GET with `?seed=`),
export-from-meeting (POST), edit (GET link), delete (POST + confirm).

## Menu integration (`base.html`)

Inside the Meetings dropdown, after the Roster `<li>` (line 358), add a
permission-gated Template Manager item:

```jinja
{% if is_authorized(Permissions.MEETING_MANAGE) %}
<li class="menu-divider"></li>
<li class="{% if request.endpoint and request.endpoint.startswith('template_manager_bp') %}submenu-active{% endif %}">
  <a href="{{ url_for('template_manager_bp.list_templates') }}">
    <i class="fas fa-layer-group"></i> {{ _('Template Manager') }}
  </a>
</li>
{% endif %}
```

Update the `meetings_active` set on `base.html:317` to also include
`template_manager_bp`. The sidebar/mobile nav (lines 94-137) does not get a
new entry — the dropdown is sufficient and matches how `Lucky Draw` lives.

## Cleanup

| File | Remove |
| --- | --- |
| `app/agenda_routes.py:1233-1303` | `export_meeting_template` view |
| `app/agenda_routes.py:1306-1348` | `delete_meeting_template` view |
| `app/agenda_routes.py:1546-1548, 1559-1560, 1596-1598` | Inline `get_col` and `local_safe_int` helpers in `_generate_logs_from_template` — replace with module-level helpers in the new service and use `parse_template_rows` |
| `app/models/meeting.py:14-65` | `Meeting.get_template_path` and `Meeting.get_type_to_template` (and the hardcoded fallback dict) |
| `app/templates/agenda.html:207` | `<button id="export-template-btn">` (and the surrounding `{% if is_authorized(Permissions.MEETING_MANAGE) %}` block if it becomes empty) |
| `app/static/js/agenda.js:373-406` | The `exportTemplateBtn` click handler |
| `app/static/js/agenda.js:3173-3200` | `window.deleteMeetingTemplate` |
| `app/static/mtg_templates/` | The whole directory — its 6 CSVs are first copied into `app/static/club_resources/0/templates/` |

The seeding logic that currently lives in `Meeting.get_type_to_template`
(`meeting.py:36-43`) moves into the service and is called from the new list
endpoint on first visit, not from `Meeting` access.

## Files to modify (concrete list)

- `app/services/meeting_template_service.py` (new)
- `app/template_manager_routes.py` (new)
- `app/templates/template_manager/list.html` (new)
- `app/templates/template_manager/editor.html` (new)
- `app/static/js/template_manager.js` (new)
- `app/static/css/template_manager.css` (new)
- `app/__init__.py` — register `template_bp`
- `app/templates/base.html` — add menu item, update `meetings_active`
- `app/models/meeting.py` — delete `get_template_path`, `get_type_to_template`
- `app/agenda_routes.py` — delete `export_meeting_template`,
  `delete_meeting_template`; refactor `_generate_logs_from_template` to call
  `meeting_template_service.parse_template_rows`; update any callers of
  `Meeting.get_type_to_template` to use the service's `list_templates`
- `app/templates/agenda.html` — remove the export button
- `app/static/js/agenda.js` — remove the export/delete handlers
- `app/static/club_resources/0/templates/` — receive 6 CSVs from `mtg_templates/`
- `app/static/mtg_templates/` — delete after copy

## Verification

Manual (the only practical path, since this is a UI feature):

1. List page shows only the current club's CSVs (switch clubs in the club
   switcher to confirm scoping).
2. Open each template → table rows match the CSV exactly (count, order,
   hidden flags).
3. Add blank row + Save → row appears in CSV (`cat` to confirm).
4. Edit a cell + Save → CSV on disk changes.
5. Move Up / Down → CSV row order changes; create-from-template reproduces
   the new order.
6. Delete a row + Save → row absent from CSV on next load.
7. Copy from seed (`/meetings/templates/new?seed=keynote_speech.csv`) → new
   file appears in the club dir with identical bytes to the seed.
8. Export from meeting → file appears, then editor opens with the meeting's
   sessions.
9. Delete template → file removed; reopening
   `/meetings/templates/edit/<deleted>` returns 404.
10. Without `MEETING_MANAGE`: menu item hidden; hitting `/meetings/templates`
    returns 403.
11. Path-traversal: `POST /meetings/templates/delete` with
    `name=../../toastmasters.db` returns 400 (rejected by
    `sanitize_filename` + `os.path.commonpath`).
12. Atomic write: kill the Flask worker mid-Save → CSV is not corrupted (the
    `.tmp` was never replaced).
13. Regression: `POST /agenda/create` with a template still produces the same
    `SessionLog` set as before the refactor.

Automated (where the project already has tests):

- Run the existing `api_tests/` suite to confirm no regressions in
  agenda/booking flows.
- Add unit tests for `meeting_template_service`:
  - `sanitize_filename` cases: spaces→`_`, leading dot, `/`, `..`, empty
  - `list_templates` filters `.*` and non-`.csv`
  - `save_template` atomic write (mock `os.replace`)
  - `get_template` on malformed CSV returns empty rows, no exception
  - Path-traversal: `_safe_join(1, '../../etc/passwd')` raises
    `TemplatePathEscape`
