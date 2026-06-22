# Plan: Generalized "Programs" — extends Planner for new-member orientation & beyond

## Context

Today the `/planner` page only handles **meeting-based bookings** (Speaker / Evaluator at a specific meeting). Each `Planner` row is owned by one `User`, scoped by `MEMBERS_SELF`, and lacks any grouping or shared-access concept. We need to add a second use case: **per-member orientation/milestone programs** (new-member onboarding, member-growth tracks, etc.) where:

- A program template holds an ordered list of tasks, some **auto-detected** from existing data (e.g., Ice Breaker completion, pathway selection) and some **manual checkboxes**.
- Each member's enrollment in a program is **shared** between mentee, assigned mentor, and admins — both can view and toggle tasks.
- Enrollment progress drives a "program complete" signal when all required tasks are checked.
- Templates are **admin-editable** in the database (not hardcoded), so the VPE can add custom programs beyond orientation.

The user wants this **on the revamped `/planner` page** (so existing meeting plans and program enrollments live in one place), with the **Planner model generalized** to fit any program — not just orientation.

This complements (does not replace) the existing meeting-based planner. Both share the `/planner` page and the `Planner` table; new rows simply have nullable meeting fields and a nullable `enrollment_id` FK.

## Approach (high level)

1. Add three new tables: `programs`, `program_tasks`, `program_enrollments`.
2. Extend `Planner` with nullable `enrollment_id`, `program_task_id`, `auto_completed`, `completed_at`, `completed_by_id`; relax `meeting_id` / `meeting_role_id` / `project_id` to nullable.
3. Service layer `app/services/program_service.py` handles enrollment creation (seeds Planner rows from template), auto-completion evaluation, and progress.
4. New permissions `PROGRAMS_SELF` (own enrollments) and `PROGRAMS_MANAGE` (templates + any enrollment).
5. Revamp `/planner` page: top section = enrollment cards (with progress + mentor + Open button), bottom section = standalone meeting plans (existing). Drill-down page per enrollment. Mentor / Admin view toggles.
6. New `/programs` admin page to CRUD templates and tasks.

## Data model

### New: `app/models/program.py`

**`Program`** (template) — `id`, `club_id` FK nullable (null = global), `name` str(120), `description` text, `is_active` bool, `display_order` int, `created_by_id` FK users, `created_at`, `updated_at`. Relationship `tasks` ordered by `display_order, id`, cascade `all, delete-orphan`.

**`ProgramTask`** (template item) — `id`, `program_id` FK, `title` str(200), `description` text, `phase_label` str(60) nullable (e.g. "Month 1"), `display_order` int, `completion_type` str(30) (`'manual' | 'sessionlog' | 'pathway_selected' | 'mentor_assigned' | 'speech_log_submitted' | 'ice_breaker'`), `completion_config` JSON nullable, `is_required` bool default True, timestamps.

**`ProgramEnrollment`** (instance) — `id`, `program_id` FK, `user_id` FK (mentee), `mentor_user_id` FK nullable, `mentor_contact_id` FK nullable, `club_id` FK, `status` (`'active' | 'paused' | 'completed' | 'cancelled'`), `started_at`, `completed_at`, `notes`, `created_by_id`, timestamps. `UniqueConstraint('program_id','user_id','club_id')`. Relationships to `program`, `mentee`, `mentor`, `mentor_contact`, and `planner_entries` (backref).

### Extend: `app/models/planner.py`

- Make `meeting_id`, `meeting_role_id`, `project_id` nullable (drop NOT NULL only — no backfill of existing rows).
- Add nullable FK `enrollment_id` → `program_enrollments.id` (indexed, ON DELETE SET NULL).
- Add nullable FK `program_task_id` → `program_tasks.id`.
- Add `auto_completed` bool default False, `completed_at` datetime nullable, `completed_by_id` FK users nullable.
- Add relationships `enrollment`, `program_task`.

## Migrations

One Alembic file at `migrations/versions/<rev>_add_programs_and_planner_relations.py`, `down_revision='fd62535f1761'` (the current latest). Use `op.create_table(...)` for the three new tables + `UniqueConstraint`. For `planner`, use `op.batch_alter_table('planner', table_kwargs=...)` to:
- `alter_column` `meeting_id`, `meeting_role_id`, `project_id` to nullable
- `add_column` for the five new fields
- `create_index` `ix_planner_enrollment_id`, `ix_planner_program_task_id`
- `create_foreign_key` for the three new FKs

Seed the two new permissions (`PROGRAMS_SELF`, `PROGRAMS_MANAGE`) and grant them to appropriate roles (mirror `migrations/versions/fd62535f1761_add_upload_links_table.py`).

## Permissions

Add to `app/auth/permissions.py` `Permissions` class:
- `PROGRAMS_SELF = 'PROGRAMS_SELF'` — own enrollments + /planner page
- `PROGRAMS_MANAGE = 'PROGRAMS_MANAGE'` — template CRUD + any enrollment + enrollment creation

Update `app/planner_routes.py` `before_request` `check_planner_enabled` to require `PROGRAMS_SELF` (replacing `MEMBERS_SELF`).

## Service: `app/services/program_service.py`

- `create_enrollment(program, user_id, club_id, mentor_user_id, mentor_contact_id)` — creates `ProgramEnrollment` + one `Planner` row per `ProgramTask` in a single transaction (status='draft', `auto_completed=False`, links `enrollment_id` + `program_task_id`).
- `evaluate(planner_row, enrollment) -> (bool completed, datetime completed_at | None)` — runs the rule for each `completion_type`. Reuse `User.get_contact(club_id)` and `SessionLog`/`Project` joins (see existing patterns in `app/speech_logs_routes.py`).
- `toggle_task(planner_id, actor_user) -> Planner` — for `manual` types only. Sets `status`, `completed_at`, `completed_by_id`. For auto types, rejects (UI keeps checkbox disabled) — completion flows through `bulk_refresh`.
- `bulk_refresh(enrollment)` — re-runs `evaluate` over every planner row. Called on enrollment-detail GET and after every toggle. Uses `ix_planner_enrollment_id`.
- `progress(enrollment) -> {done, total, required_done, required_total, percent}`.

## Routes

### Revise `app/planner_routes.py` (blueprint `planner_bp`)

- `GET /planner` — load enrollments (visibility-scoped, see below) + standalone `Planner` rows (`enrollment_id IS NULL AND user_id = current_user.id`). Render `planner.html` with `enrollments`, `plans`, `view_mode`.
- Existing CRUD endpoints (`POST/PUT/DELETE /api/planner/...`, `/api/planner/<id>/cancel`) stay; restrict to non-program rows OR admin.
- New `POST /api/planner/<plan_id>/toggle-complete` — mentee/mentor/admin; calls `program_service.toggle_task`.
- New `GET /planner/enrollment/<enrollment_id>` — drill-down page (`program_enrollment.html`).

### New `app/program_routes.py` (blueprint `program_bp`, prefix `/api`)

- `GET /programs` — list templates (own club + global `club_id IS NULL`). `PROGRAMS_MANAGE`.
- `POST /programs`, `PUT /programs/<id>`, `DELETE /programs/<id>` — template CRUD. `PROGRAMS_MANAGE`. Delete = soft (`is_active=False`).
- `POST /programs/<pid>/tasks`, `PUT /programs/<pid>/tasks/<tid>`, `DELETE /programs/<pid>/tasks/<tid>` — task CRUD. `PROGRAMS_MANAGE`.
- `GET /program-enrollments` — `PROGRAMS_SELF` OR `PROGRAMS_MANAGE`, visibility-scoped.
- `POST /program-enrollments` — `PROGRAMS_MANAGE`. Body `{program_id, user_id, mentor_user_id?, mentor_contact_id?, club_id}`.
- `PUT /program-enrollments/<id>` — mentor OR admin; update mentor / status / notes.
- `GET /program-enrollments/<id>` — visibility-scoped. Returns enrollment + task list with auto/manual status, completed_at, completed_by.
- `POST /program-enrollments/<id>/tasks/<planner_id>/toggle` — visibility-scoped.

### Visibility rule (helper, used in every list/get)

```
if has_permission(PROGRAMS_MANAGE): return all in club
elif current_user.id == e.mentor_user_id: return where mentor_user_id = me
else: return where user_id = me
```

### Page route

- `GET /programs` — `PROGRAMS_MANAGE`. Renders `app/templates/programs.html` (template admin UI).

Register `program_bp` in `app/__init__.py` next to `planner_bp`.

## UI changes

### `/planner` revamp (`app/templates/planner.html`)

- Header: title "Programs & Planner"; pill toggle `Mine | As Mentor | All (admin)` (admin sees all three).
- Top section `#enrollments-section` — grid of `.program-card` per enrollment:
  - Header: program name, status badge, "Mentor: <name> — not assigned" line.
  - Body: progress bar (reuse `_level_progress.html` styling + `is-completed` / `is-in-progress` classes) + "X / Y tasks" + phase chips (`Month 1`, `Month 2`).
  - Footer: "Open" button → drill-down.
- Below: existing planner table, filtered to standalone rows.
- Admin right rail: "Manage Templates" link to `/programs`; "New Enrollment" button → opens `partials/_enrollment_modal.html`.

### Drill-down (`app/templates/program_enrollment.html`, route `planner_bp.enrollment_detail`)

- Header: program name, mentee, mentor block (edit pencil for mentor/admin).
- Task list grouped by `phase_label` (or `Ungrouped`).
- Each row: checkbox (disabled when `completion_type != 'manual'`), title, description tooltip, badge `Manual` / `Auto` (auto has `fa-magic` icon + tooltip "Auto-detected from {source}"), `completed_at` timestamp, `completed_by` name.

### `/programs` admin (`app/templates/programs.html`)

- List of templates with `is_active` toggle, edit button.
- `partials/_program_template_modal.html` — name, description, is_active, ordered task editor (numbered with up/down arrows).
- Each task row inline-edits: title, `completion_type` dropdown + conditional `completion_config` textarea (JSON).

### Modals (new partials)

- `app/templates/partials/_enrollment_modal.html` — pick member (uses `custom_select.js` + `populate_users`), pick program (filtered to active), pick mentor (Contact select; pre-suggests current `UserClub.mentor_id`), notes.
- `app/templates/partials/_program_template_modal.html` — template editor.

### Nav (`app/templates/base.html`)

Add nav entry "Programs" → `/programs` gated on `PROGRAMS_MANAGE`, placed beside the existing "Planner" entry. Update "Planner" entry label to "My Plans" so the split is visually clear. Mirror in mobile submenu.

## CSS / JS

- **Extend** the four `app/static/css/pages/planner/planner-{base,desktop,ipad,mobile}.css` files — add a `/* === Programs section === */` block with `.program-card`, `.enrollment-header`, `.task-row`, `.badge-auto`, `.badge-manual`, `.mentor-line`. Register in `app/assets.py` `css_all` bundle (already there).
- **Extend** `app/static/js/planner_modal.js` with `openEnrollmentModal`, `openEnrollmentDetail`, `loadEnrollmentTasks`, `toggleTask`, `switchView`.
- **New** `app/static/js/program_admin.js` — small — task-list reorder (up/down buttons), completion-type ↔ config-field visibility toggle, save.
- Cache-bust via existing `?v={...|static_version}` filter.

## i18n

Add to `app/templates/...` and `app/translations/zh_CN.json` together (one PR):

- `"Programs"`, `"Programs & Planner"`, `"My Plans"`, `"As Mentor"`, `"All Enrollments"`
- `"New Enrollment"`, `"Manage Templates"`, `"Template"`, `"Task"`, `"Phase"`
- `"Completion Type"`, `"Manual"`, `"Auto-detected"`, `"Auto-detected from {source}"`
- `"Mentor"`, `"Mentor: not assigned"`, `"Pick mentor"`, `"Pick program"`
- `"Add Task"`, `"Edit Task"`, `"Move up"`, `"Move down"`
- `"Program complete"`, `"Active"`, `"Paused"`, `"Cancelled"`
- `"Tasks ({done}/{total})"`, `"Required ({done}/{total})"`

## Phased rollout (each phase = 1 PR)

- **A — Templates + migrations** (1 PR): models + migration + permission seed + `program_bp` template CRUD + `/programs` admin page + `program_admin.js`.
- **B — Enrollments + /planner revamp (read-only)**: enrollment endpoints + `create_enrollment` seeding + `/planner` cards + drill-down + mentor visibility.
- **C — Completion + progress**: `evaluate`, `toggle_task`, `bulk_refresh` + toggle endpoint + UI checkboxes + progress bar wiring.
- **D — Mentor UX + admin polish**: view toggle, mentor-edit-enrollment, empty-state polish, flash messages.
- **E — i18n + docs + tests**: zh-CN translations, CLAUDE.md update, end-to-end browser smoke test, full pytest suite via `make test-fast`.

## Critical files

- `app/models/program.py` (new)
- `app/models/__init__.py` (export new models)
- `app/models/planner.py` (extend)
- `app/planner_routes.py` (revise `before_request`, add drill-down + toggle endpoint)
- `app/program_routes.py` (new blueprint)
- `app/__init__.py` (register `program_bp`)
- `app/auth/permissions.py` (add `PROGRAMS_SELF`, `PROGRAMS_MANAGE`)
- `app/services/program_service.py` (new)
- `app/templates/planner.html` (revamp)
- `app/templates/program_enrollment.html` (new)
- `app/templates/programs.html` (new)
- `app/templates/partials/_enrollment_modal.html` (new)
- `app/templates/partials/_program_template_modal.html` (new)
- `app/templates/base.html` (nav entry)
- `app/static/css/pages/planner/planner-*.css` (extend)
- `app/static/js/planner_modal.js` (extend)
- `app/static/js/program_admin.js` (new)
- `app/translations/zh_CN.json` (extend)
- `migrations/versions/<rev>_add_programs_and_planner_relations.py` (new)
- `tests/test_programs_models.py`, `tests/test_programs_routes.py`, `tests/test_planner_enrollment_integration.py` (new)

## Reuse & invariants to honor

- **Batch loaders**: `Contact.populate_users` / `populate_primary_clubs` (`app/models/contact.py:417`) for any enrollment list — never per-row property access in a loop.
- **`User.ensure_contact(club_id)`** when creating an enrollment for a user without a Contact.
- **`_level_progress.html` styling** + `.is-completed` / `.is-in-progress` CSS vocabulary for the progress UI (`app/templates/partials/_level_progress.html`).
- **`populate_users` + custom_select.js** for the member/mentor picker (no new selector widget).
- **Plain `fetch()` + JSON endpoints** for all new interactions (no full-page POST).
- **Flash messages** (`success` / `error` / `info`) for feedback; no Bootstrap toasts.
- **`MEMBERS_SELF` semantics preserved** for the existing meeting-based planner rows — only the `/planner` route gate switches to `PROGRAMS_SELF`. The planner module stays `is_module_enabled('Planner')` (don't rename in this PR to avoid breaking club settings).
- **`docs/CONTACT_USER_CLUB_MODEL.md`** must be read before any work touching the user/contact split.

## Risks & edge cases

- **Meeting fields go nullable**: existing rows are unchanged; no backfill. Verify with a smoke query that legacy rows still load after migration.
- **Mentor without User account**: store both `mentor_user_id` (nullable) and `mentor_contact_id` (nullable); require at least one. Visibility rule uses `mentor_user_id` for login-based access; flag as TODO if guest-mentor login is ever added.
- **Duplicate enrollments** blocked by `UniqueConstraint('program_id','user_id','club_id')`. Re-enrollment after `cancelled` requires flipping status first.
- **Auto-detect project_code**: `Project.Code` (e.g. Ice Breaker) — confirm the field name against `app/models/project.py` before wiring.
- **JSON column**: use `db.JSON` (works on MySQL + SQLite).
- **Toggle race**: wrap `toggle_task` in a single-row read-modify-write; `bulk_refresh` is idempotent so a second call is safe.
- **Migration table_kwargs**: load from app factory per `migrations/env.py` convention; pass `None` for SQLite-only is acceptable.

## Verification

1. `make db-upgrade` — migration runs cleanly; existing planner rows unchanged.
2. `make test-fast` — full suite passes; new tests cover template CRUD, enrollment visibility matrix, and the auto-detect truth table per `completion_type`.
3. Manual smoke (use the existing `make run` on `:5001`):
   - As admin: visit `/programs`, create a "New Member Orientation" template with the 13 example tasks (mix of manual + auto), reorder, save.
   - Open `/planner`, click "New Enrollment", pick a member + the new template + a mentor. Verify one Planner row per task appears, grouped under the enrollment card.
   - Drill in: toggle a manual task → progress increments + timestamp + actor recorded.
   - Submit a SessionLog for the mentee matching `ice_breaker` config → `bulk_refresh` flips the auto task to completed.
   - Switch toggle to "As Mentor" → mentor sees only their mentees' enrollments.
   - Switch to non-mentor non-admin → sees only their own.
   - Switch locale to `zh_CN` → all new strings render in Chinese.
4. Browser check: progress bar reflects done/total, mentor name displayed, "Program complete" badge appears when all required tasks done.