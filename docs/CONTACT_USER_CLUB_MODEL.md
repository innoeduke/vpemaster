# Contact / User / Club Data Model — Design Logics

> **Status**: source of truth for the data model. If implementation disagrees
> with this doc, fix the code, then update the doc in the same change.
>
> **How to use**: agents (human or AI) implementing or reviewing a feature
> that touches `users`, `Contacts`, `user_clubs`, or `contact_clubs` should
> verify their work against the rules below. Code anchors are pinned to
> file:line so reviewers can jump straight to the relevant source.

## Core entities

| Table            | Scope        | One row per...                              | Has FK to user?              |
|------------------|--------------|---------------------------------------------|------------------------------|
| `users`          | system-wide  | system user account                         | n/a                          |
| `Contacts`       | global       | person's global contact card                | indirect (via `user_clubs.contact_id`) |
| `user_clubs`     | per club     | user's membership in a specific club        | **yes** (`user_id` required) |
| `contact_clubs`  | per club     | contact's membership in a specific club     | via `contact_id` only (not direct) |

- **`users`** is the system identity. A user account always exists before any
  club-specific state.
- **`Contacts`** is the global contact card. It carries personal info
  (name, email, phone, bio, pathway, etc.) and its own home club
  (`Contact.home_club`) that follows the person across clubs.
- **`user_clubs`** is a junction: which clubs a user belongs to, plus
  per-club state: `auth_role_id`, `is_home` (the user's *system-level*
  home club), `mentor_id`, `current_path_id`. This is also where the
  user↔contact link lives (`contact_id`).
- **`contact_clubs`** is **broader**: it holds memberships for BOTH
  user-linked contacts AND pure-guest contacts (people added by a club
  who never created an account). This is how a club can have members who
  don't appear in `users`.

## The rules

### 1. There are two home-club concepts — they are NOT the same

| Concept               | Where it lives                                | Who sets it                    | What it drives                                                     |
|-----------------------|-----------------------------------------------|--------------------------------|--------------------------------------------------------------------|
| **User.home_club**    | `UserClub.is_home = True` for that `user_id`  | the user (or admin approval)   | auth (`is_home_club_admin`), login, current club context, profile, about-club member directory |
| **Contact.home_club** | `Contact.home_club` (text column)             | a clubadmin on the contact card | contacts page display, clubadmin-curated "where this person is from" |

They are **independent attributes**. They CAN have the same value, but they
do not have to. They drift independently and that's by design. A user can
move clubs (changing `User.home_club`); the contact's home club stays put
unless a clubadmin explicitly edits it. A guest contact has
`Contact.home_club` set by a clubadmin and no `User.home_club` at all.

**Don't sync them automatically.** If a feature wants to align them, it
must do so as an explicit, user-initiated "copy from user" action — never
a background job or trigger.

### 2. The home-club derivation chain — what each consumer reads

```
# User-level (auth, login, profile, about-club, club context):
User
  → UserClub where is_home = True   (via User.home_club)
  → Club

# Contact-level (contacts page, clubadmin curation):
Contact.home_club                    (a text column on Contacts)
```

`Contact.get_home_club()` (the property the contacts page consumes)
reads from `Contact.home_club` directly — it does NOT route through the
user. This is what makes the empty-state contract work for guest
contacts (see rule 4).

For the `User.home_club` chain:
- `User.home_club` (`app/models/user.py:394-399`) returns the `UserClub`
  where `is_home=True`, then `.club`.
- `User.set_home_club()` (`app/models/user.py:401-418`) flips all of a
  user's `UserClub` rows to `is_home=False` before setting one to `True`.
  **This is the only sanctioned way to set the user-level flag.** Never
  set `is_home=True` on multiple rows for the same user.

For the `Contact.home_club` chain:
- It's a direct column on `Contacts`. No joins, no derivation, no user
  lookup.
- The form offers a picker sourced from `clubs` (active only) and a
  free-text fallback for inactive clubs that aren't in our DB.

### 3. Primary club vs home club — three different concepts, keep them straight

| Concept            | Source                                          | Meaning                                                                  |
|--------------------|-------------------------------------------------|--------------------------------------------------------------------------|
| **User.home_club** | `User.home_club` (via `user_clubs.is_home`)     | The user's designated system-level home club. Auth-relevant.             |
| **Contact.home_club** | `Contact.home_club` (text column)            | The contact card's home club, as edited by a clubadmin. Display-level.   |
| **Primary club**   | `Contact.get_primary_club()`                    | The **first** `ContactClub` row for the contact — not authoritative      |

The third one (`get_primary_club`) is a separate imperfect concept — it
returns the first `ContactClub` row, with no preference logic. Do not
treat it as a substitute for either home club. See "Open questions".

### 4. Empty-state contract
- A contact with no `Contact.home_club` value renders "—" in the UI.
  Do NOT default to the current club, do NOT fall back to
  `User.home_club` (that's a different concept), do NOT guess.
- A user with no `UserClub(is_home=True)` row returns `None` from
  `User.home_club`. Don't fabricate one.

### 5. `is_home` invariant (UserClub level)
At most one `UserClub` row per `user_id` has `is_home=True`. Enforce this
by always going through `User.set_home_club()`. If a pre-existing data
anomaly shows up (multiple `True` rows for one user), `User.home_club`
returns the first one found — fix the data, don't special-case the code.

### 6. `Contact.home_club` is plain text, intentionally
It's a text column, not an FK to `clubs`, by design:
- It supports inactive clubs that don't have a row in our `clubs` table
  (Toastmasters has thousands of clubs; we don't pre-populate them).
- It avoids two-sources-of-truth: the value here is *the* value, not a
  pointer to a row that could be edited or deleted out from under us.
- The form's picker is sourced from `clubs` for active options AND
  offers a free-text input for inactive clubs. Whatever the user picks
  is stored as the text value.

If we later need joins (e.g., "all contacts whose home club is district
X"), we can add a `home_club_id` FK and a sync rule. Until then, plain
text is the right primitive.

### 7. Avatar ownership — User vs Contact are two independent fields

**Invariant:** `User.avatar_url` and `Contact.Avatar_URL` are two separate
fields. They are *not* mirrors of each other and may legitimately diverge.

| Owner       | Field             | Drives display in...                                      |
|-------------|-------------------|-----------------------------------------------------------|
| `users`     | `avatar_url`      | User profile chrome (header avatar, profile page, "Change Photo" button) |
| `Contacts`  | `Avatar_URL`      | Club-context UI: roster rows, agenda owner chips, meeting card avatars, anything tied to a specific club |

**Why two fields, not one:** A user may legitimately present different
photos in different clubs (formal headshot at the home club, casual photo
in a social club, no photo as a guest). Club context drives the visual
identity within that club; the User record drives identity on the
user's own profile surfaces.

**Conversion rule (one-way, at creation time only):** When a contact is
converted to a user, the contact's `Avatar_URL` is mirrored to the new
user's `avatar_url` so the profile isn't empty. After that, the two
fields drift independently — editing one does NOT update the other.

| Code anchor                                            | What it does                                       |
|--------------------------------------------------------|----------------------------------------------------|
| `app/models/user.py:35` (`avatar_url` column)          | The User's own profile photo                       |
| `app/models/contact.py` (`Avatar_URL` column)          | The Contact's club-context photo                   |
| `app/users_routes.py` (`_save_user_data`, contact link)| One-way mirror on contact-to-user conversion       |

**Anti-pattern to avoid:** do NOT collapse these into a single column, and
do NOT add a SQLAlchemy event listener that auto-syncs them. They are
deliberately independent, and "fixing" the duplication would remove the
ability to show different photos per club.

## Code anchors

| Concept                                  | File : Line                          |
|------------------------------------------|--------------------------------------|
| `User.home_club`                         | `app/models/user.py:394-399`         |
| `User.set_home_club`                     | `app/models/user.py:401-418`         |
| `User.contact_id` (back-compat)          | `app/models/user.py:133-139`         |
| `Contact.user_id` / `Contact.user`       | `app/models/contact.py:132-169`      |
| `Contact.get_home_club`                  | `app/models/contact.py:392-407` — reads from `Contact.home_club` directly, returns the text value (or None). Does NOT route through the user. |
| `Contact.home_club` (column)             | `app/models/contact.py` (column definition); migration `migrations/versions/c1d2e3f4a5b6_add_contact_home_club.py` (schema + backfill). |
| `Contact.get_primary_club`               | `app/models/contact.py:381-390`      |
| `UserClub.is_home` column                | `app/models/user_club.py:50`         |
| `Contact.populate_users` (batch pattern) | `app/models/contact.py:413-435`      |
| `Contact.populate_primary_clubs`         | `app/models/contact.py:437-468`      |
| `is_home_club_admin` auth check          | `app/users_routes.py:42-44, 288-298` |
| Login-time `is_home` marking             | `app/auth/routes.py:46-65, 255-263`  |
| Current club context fallback            | `app/club_context.py:74`             |
| About-club home/visiting display         | `app/templates/about_club.html:239-249` |
| Contact edit modal — home club selector  | `app/templates/_contact_modal.html:85-86` |
| Home club form population (JS)           | `app/static/js/main.js:242-275`      |

## Verification checklist

When implementing or reviewing a feature in this area, confirm:

- [ ] **Two home clubs exist and you know which one you want.** If the
      feature is contact-display (contacts page, contact card, roster
      table), use `Contact.home_club`. If it's user-display (profile,
      auth, login, current club context), use `User.home_club`. Do not
      mix them.
- [ ] **No automatic sync between the two home clubs.** If a form
      offers a "use user's home club" button, the action is a one-shot
      copy, not a live link. The fields stay independent afterward.
- [ ] **Empty states are explicit.** A null `Contact.home_club` renders
      "—". A null `User.home_club` returns `None` cleanly. Never default
      to a plausible value.
- [ ] **`is_home` writes go through `set_home_club`.** Never set
      `is_home=True` on a single row directly.
- [ ] **Authorization uses `User.home_club`, not `Contact.home_club`.**
      The `is_home_club_admin` gate must read the user-level attribute;
      it is not safe to derive it from a contact-card value that a
      clubadmin can edit.
- [ ] **No N+1 on contact home club in list views.** `Contact.home_club`
      is a column on the row, so a normal `Contact.query` already
      carries it. No populate helper needed for v1. (If we later add
      a `home_club_id` FK with joins, add a populate helper at that
      point.)
- [ ] **No pre-population of inactive clubs in `clubs`.** Don't add
      thousands of placeholder club rows. The `Contact.home_club`
      text field is how we represent inactive clubs.

## Open questions / known gaps

1. **`Contact.get_primary_club()` is not authoritative.** It returns the
   first `ContactClub` row, with no preference. There is no `is_primary`
   flag on `contact_clubs`. If/when a true "primary club for a contact"
   is needed, the model needs an explicit column (likely on
   `contact_clubs`).
2. **No "sync from user.home_club" workflow on contact creation.** When
   a user-linked contact is created, do we copy `User.home_club` to
   `Contact.home_club` automatically? Currently no — they're independent.
   If a UX case emerges where this is annoying, add an explicit "sync"
   action, not a default copy.
3. **Free-text home club = no district/area rollups.** If we ever need
   "all contacts whose home club is in district X", a text field can't
   answer that. Solutions: a `home_club_id` FK on `Contacts` (sync
   required), or a `home_club_district` text column, or a separate
   `home_clubs` lookup table. Decide when the need arises, not now.
4. **Legacy data migration**: implemented. The
   `c1d2e3f4a5b6_add_contact_home_club` migration backfills
   `Contact.home_club` from `User.home_club.club_name` for any contact
   with a `UserClub(is_home=True)` row. Pure-guest contacts stay null.
   After migration, the two fields drift independently per design.
