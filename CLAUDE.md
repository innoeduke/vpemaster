# CLAUDE.md

Flask app for Toastmasters club management (meetings, agendas, Pathways speech tracking, role booking/waitlists, in-meeting voting, AI chat assistant). Production.

## Commands

Prefer Makefile targets — they wrap pytest with the right flags. The Makefile is the source of truth for the full list.

```bash
make run                          # dev server on :5001
make run-prod                     # gunicorn (matches deploy setup)
make test-fast                    # parallel pytest — preferred for full suite
```

## CSS — z-index

Use the tiers in `docs/ZINDEX_SCALE.md` (definitive). Lint: `npm run lint:css` (stylelint enforces token usage and tier-permitted paths). Regression tests: `tests/test_zindex_stacking.py` (static) and `tests/test_dropdown_stacking_browser.py` (browser smoke, skipped if Chrome unavailable).

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

### Multi-club context

Active club is tracked in `session['current_club_id']` via `app/club_context.py`. `get_or_set_default_club()` resolves per request: URL query param → session → user's home club → first club. `@authorized_club_required` gates club-scoped routes.

### Models (`app/models/`) — one file per domain

`Club`, `User`, `Contact`, `UserClub`, `ContactClub`, `Meeting`, `SessionType`, `SessionLog`, `Roster`, `RosterRole`, `MeetingRole`, `Waitlist`, `Vote`, `Achievement`, `Planner`, `ChatMessage`, plus `Project` / `Pathway` / `PathwayProject` for the Pathways catalog. User ↔ Contact link per club through `UserClub`; `User.ensure_contact()` creates or links a Contact when a user joins a club.

### Permission system (`app/auth/`)

Flask-Principal RBAC. Roles ordered by level: SysAdmin → ClubAdmin → Operator → Staff → Member → Guest. Fine-grained constants in `Permissions` (e.g., `MEETING_MANAGE`, `ROSTER_EDIT`, `CHAT_AI`); per-club overrides via `club_permissions`. `User.has_club_permission(perm, club_id)` checks role permissions + sharing-master override for meetings. Decorators: `@any_permission_required(...)`, `@all_permissions_required(...)`, `@role_required(...)`.

### Routes & services

One blueprint per file in `app/` (agenda, booking, voting, contacts, speech logs, pathways, achievements, planner, chat, roster, tools, settings, auth, …). Business logic in `app/services/` — chat (Anthropic integration, tool calling, sliding-window context), achievement credentials, role booking, backup, PPTX slides, exports, meeting templates.

### Frontend assets

CSS files follow `*-base.css`, `*-desktop.css`, `*-ipad.css`, `*-mobile.css`. Flask-Assets bundles with `cssmin` (`app/assets.py`). JS in `app/static/js/`. Jinja2 templates use `_()` translations and the `static_version` filter for cache busting.

## See also

- `AGENTS.md` — vpemaster agent guidelines (longer-form conventions with examples)
- `docs/CONTACT_USER_CLUB_MODEL.md` — users/Contacts/user_clubs/contact_clubs model and the two home-club concepts (`User.home_club` vs `Contact.display_club_name`). **Read for any feature touching contacts, members, or club membership.**
- `docs/MAILBOX_REALTIME_DESIGN.md` — SSE real-time notifications, `MessageAnnouncer` queue, WSGI deployment guidelines
