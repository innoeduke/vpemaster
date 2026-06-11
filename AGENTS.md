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
- **Per-feature decisions** (column placement, display format, scope)
  belong in the PR description, not the design doc. Design docs capture
  invariants, not implementation choices for a single feature.
