# AGENTS.md

`vpemaster` — a Toastmasters club-management tool (Flask + SQLAlchemy).

## Read first

Before implementing or reviewing a feature, read the relevant design
doc(s) under `docs/`. They are the source of truth for the data model —
if code disagrees with a doc, the doc wins; fix the code, then update
the doc in the same change.

- `docs/CONTACT_USER_CLUB_MODEL.md` — design logics for the
  `users` / `Contacts` / `user_clubs` / `contact_clubs` data model
  (home club, primary club, per-club vs global, `is_home` invariant).
  **Read this for any feature touching contacts, members, or club
  membership.**
- [docs/MAILBOX_REALTIME_DESIGN.md](file:///Users/wmu/workspace/toastmasters/vpemaster/docs/MAILBOX_REALTIME_DESIGN.md) — real-time message notification design (Server-Sent Events, MessageAnnouncer queue architecture, deployment WSGI guidelines).
- [docs/PERFORMANCE_WALKTHROUGH.md](file:///Users/wmu/workspace/toastmasters/vpemaster/docs/PERFORMANCE_WALKTHROUGH.md) — Voting and Agenda pages performance optimization history, load testing benchmarks, and SQL query count reduction analysis.

When you add new design rules, give them their own file under `docs/`
and link it here.

## Conventions

- **Code style**: match the file you're editing. Don't introduce new
  patterns without justification.
- **Batch loaders**: list-view code that reads N contacts/users/clubs
  must go through a batch populate helper. Pattern lives in
  `app/models/contact.py` (`populate_users`, `populate_primary_clubs`).
  Never call a per-row property in a tight loop.
- **Writes that touch invariants**: e.g. setting `UserClub.is_home` —
  always go through the model method (`User.set_home_club`), not raw
  column updates.
- **Empty states**: when a value is logically absent (e.g. a guest
  contact's home club), render an explicit empty marker like "—" in the
  UI. Do not default to a plausible-looking value.
- **Avoid N+1 Queries**: When building APIs or backend endpoints fetching roles or slots across multiple meetings, avoid accessing lazy relationships or dynamic properties (such as `.owner` or `.waitlists`) in loops. Instead, pre-fetch relationship IDs (e.g. from table links like `OwnerMeetingRoles`) in a single bulk query and index them in memory.
- **Jinja HTML Translations**: Jinja's translation block `{{ _('text') }}` escapes HTML tags by default. If a translation string contains HTML markup (like `<strong>` or `<a>`), always append the `| safe` filter (e.g., `{{ _('Select a <strong>role</strong>.') | safe }}`) to ensure the HTML renders correctly in the browser.
- **Info / Help Boxes**: Avoid raw inline HTML blocks for info or instruction sections. Use the reusable component macro `render_info_box` from `components/info_box.html`. Use the club theme maroon color styling (`#772432`) for titles, borders, and icons, paired with the light pink background (`#faf0f1`).
- **Per-feature decisions** (column placement, display format, scope)
  belong in the PR description, not the design doc. Design docs capture
  invariants, not implementation choices for a single feature.

