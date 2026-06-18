# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Flask app for Toastmasters club management (meetings, agendas, Pathways speech tracking, role booking/waitlists, in-meeting voting, AI chat assistant). Production.

## Commands

Prefer Makefile targets — they wrap pytest with the right flags. Raw `pytest` is fine for ad-hoc runs.

```bash
make run                          # dev server on :5001 (reads .flaskenv: FLASK_APP=run.py, FLASK_DEBUG=1)
make run-prod                     # gunicorn (matches deploy setup)

# Tests (in-memory SQLite via conftest.py)
make test-fast                    # parallel pytest — preferred for full suite
make test                         # serial pytest
make test-smart                   # only tests affected by recent changes
make test-fix                     # only tests that failed in the last run
make test-coverage                # coverage report → htmlcov/index.html
make test-watch                   # auto-rerun on file change
make test-file FILE=tests/test_agenda_routes.py
make test-class CLASS=tests/test_agenda_routes.py::TestClass
make test-method METHOD=tests/test_agenda_routes.py::TestClass::test_name
make test-chat-fast               # parallel: Anthropic-backed chat tests
make test-chat-mock               # offline: mocked chat tool tests (no API calls)

make lint                         # flake8 (optional — install flake8 first)
make format                       # black (optional — install black first)

# Database migrations (Makefile wraps flask db — prefer these)
make db-upgrade
make db-migrate MSG="description" # generates a new migration
flask db history                  # raw only — no Makefile target

# CLI
flask resources backup
flask sync
flask translate-scan

```

## Conventions (load-bearing — these have bitten us before)

- **Match the file you're editing.** Don't introduce new patterns (decorators, ORM loading styles, error handling) without justification. The codebase is intentionally heterogeneous.
- **Batch loaders, never per-row in loops.** List views reading N contacts/users/clubs must go through a batch populate helper. Pattern lives in `app/models/contact.py` (`populate_users`, `populate_primary_clubs`). Never call a per-row property in a tight loop.
- **Writes that touch invariants go through model methods.** e.g. setting `UserClub.is_home` must use `User.set_home_club()` (it flips all of a user's rows to `False` before setting one to `True`). Never raw-update the column.
- **Empty states render an explicit marker** like "—" — never default to a plausible-looking value (e.g. a guest contact's home club).
- **Design docs in `docs/` are source of truth.** If code disagrees with a doc, fix the code and update the doc in the same change.
- **Frontend styling/scripts: reuse before adding.** Before writing new CSS or JS, look up existing files in `app/static/css/` and `app/static/js/` (and the page-specific subdirs) and update them. Don't introduce parallel files for the same concern.

`AGENTS.md` has the longer-form version of these rules — read it before non-trivial changes.

## Architecture

**App factory** (`app/__init__.py`): `create_app()` wires up SQLAlchemy, Migrate, Bcrypt, Login, Principal, Mail, Assets, Cache; registers blueprints and CLI commands; sets up Flask-Principal identity loading. Reads `config.Config` (which loads `.env`).

### Database

MySQL in production, SQLite in-memory for tests. Flask-Migrate manages `migrations/versions/`. Constraint naming convention is defined in the app factory.

### Multi-club context

The app supports multiple clubs per install. Active club is tracked in `session['current_club_id']` via `app/club_context.py`. `get_or_set_default_club()` resolves per request: URL query param → session → user's home club → first club. `@authorized_club_required` gates club-scoped routes.

### Models (`app/models/`) — one file per domain

`Club`, `User`, `Contact`, `UserClub`, `ContactClub`, `Meeting`, `SessionType`, `SessionLog`, `Roster`, `RosterRole`, `MeetingRole`, `Waitlist`, `Vote`, `Achievement`, `Planner`, `ChatMessage`, plus `Project` / `Pathway` / `PathwayProject` for the Pathways catalog. User ↔ Contact link per club through `UserClub`; `User.ensure_contact()` creates or links a Contact when a user joins a club.

### Permission system (`app/auth/`)

Flask-Principal RBAC. Roles ordered by level: SysAdmin → ClubAdmin → Operator → Staff → Member → Guest. Fine-grained constants in `Permissions` (e.g., `MEETING_MANAGE`, `ROSTER_EDIT`, `CHAT_AI`); per-club overrides via `club_permissions`. `User.has_club_permission(perm, club_id)` checks role permissions + sharing-master override for meetings. Decorators: `@any_permission_required(...)`, `@all_permissions_required(...)`, `@role_required(...)`.

### Routes & services

One blueprint per file in `app/` (agenda, booking, voting, contacts, speech logs, pathways, achievements, planner, chat, roster, tools, settings, auth, …). Business logic in `app/services/` — chat (Anthropic integration, tool calling, sliding-window context), achievement credentials, role booking, backup, PPTX slides, exports, meeting templates.

### Frontend assets

Flask-Assets bundles CSS with `cssmin` (see `app/assets.py`). CSS pattern: `*-base.css`, `*-desktop.css`, `*-ipad.css`, `*-mobile.css`. JS in `app/static/js/`. Jinja2 templates with `_()` translations and the `static_version` filter for cache busting.

## See also

- `AGENTS.md` — vpemaster agent guidelines (longer-form conventions with examples)
- `docs/CONTACT_USER_CLUB_MODEL.md` — users/Contacts/user_clubs/contact_clubs model and the two home-club concepts (`User.home_club` vs `Contact.display_club_name`). **Read for any feature touching contacts, members, or club membership.**
- `docs/MAILBOX_REALTIME_DESIGN.md` — SSE real-time notifications, `MessageAnnouncer` queue, WSGI deployment guidelines
