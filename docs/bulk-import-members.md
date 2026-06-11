# Bulk Import Members

How to add multiple members at once using the Bulk Import feature.

## Location

**Members page** → top-right button group → **Bulk Import** (the blue/info button next to **Add New**).

Template: `app/templates/users.html`
Route: `app/users_routes.py:573` (`bulk_import_users`, `POST /user/bulk_import`)

## Permission

Requires the `MEMBERS_MANAGE` permission (typically held by Admins / SAA).

## Steps

1. Navigate to the **Members** page.
2. Click **Bulk Import** — this opens the hidden file picker (`#bulk-import-form`).
3. Select a `.csv` file.
4. The browser submits the file as a `multipart/form-data` POST to `/user/bulk_import`.
5. Review the flash messages after the redirect — the page reports how many users were imported plus any row-level errors.

## CSV Format

The file must have a header row (which is skipped) and up to 5 columns:

| # | Column       | Required | Notes |
|---|--------------|----------|-------|
| 1 | Fullname     | Yes      | Used to look up a matching `Contact` (linked if found) |
| 2 | Username     | Yes      | Must be unique across users |
| 3 | Member ID    | No       | Stored only |
| 4 | Email        | No       | Must be unique if provided; checked against existing users |
| 5 | Mentor Name  | No       | Used to look up a `Contact` and set as mentor (linked if found) |

### Example

```csv
Fullname,Username,Member ID,Email,Mentor Name
Jane Doe,janed,12345,jane@example.com,John Smith
Bob Lee,blee,12346,bob@example.com,
```

## Behavior

- **Default password:** `toastmasters` (users should change on first login).
- **Default role:** `Member` (resolved from `AuthRole` by name).
- **Duplicate username:** row is skipped, reported in flash error.
- **Duplicate email:** row is skipped, reported in flash error.
- **Contact linking:** if a `Contact.Name` matches `Fullname`, the new user is linked to that contact (`contact_id`).
- **Mentor linking:** if a `Contact.Name` matches `Mentor Name`, the mentor is resolved to a `mentor_id`.
- **Rows with fewer than 2 non-empty cells** are skipped silently.
- **Final summary flash:** `N users imported successfully.` plus per-row error messages.

## Errors You May See

- `No file part` — request had no `file` field.
- `No selected file` — file input was empty.
- `Invalid file type. Please upload a .csv file.` — file did not end in `.csv`.
- `You don't have permission to perform this action.` — caller lacks `MEMBERS_MANAGE`.
- `Skipping row: Fullname and Username are mandatory. Row: ...`
- `Skipping user '<username>': User already exists.`
- `Skipping user '<username>': Email '<email>' is already registered.`

## Related

- There is no companion "Export members" button in the UI. Use the Members page table's existing export (if available) or query the database directly.
- The CLI command `flask import-data` (in `app/commands/import_data.py`) is a **separate, much broader** importer — it loads a full SQL backup for a club, not a member CSV. Do not use it for routine member onboarding.
