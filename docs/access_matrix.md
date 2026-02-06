# Access Control Matrix

This document defines the access control rules for VPEMaster based on user roles and meeting statuses.

## User Roles

The system supports the following roles in hierarchical order:

| Role | Level | Description |
|------|-------|-------------|
| **Admin** | 10 | Full system access, can manage all settings and users |
| **Operator** | 5 | Can manage meetings, bookings, and view results |
| **Staff** | 2 | Can view unpublished meetings and voting results |
| **User** | 1 | Standard member, can book own roles and view public content |
| **Guest** | 0 | Unauthenticated users, limited to public content |

## Meeting Statuses

Meetings progress through the following statuses:

1. **Unpublished** - Meeting created but not visible to members
2. **Not Started** - Published meeting, visible to all, booking open
3. **Running** - Meeting in progress, voting enabled
4. **Finished** - Meeting completed, results visible
5. **Cancelled** - Meeting cancelled

## Access Matrix by Route

### Agenda (`/agenda`)

| Role | Unpublished | Not Started | Running | Finished |
|------|-------------|-------------|---------|----------|
| **Guest** | 302 → `/meeting-notice` | 200 ✓ | 200 ✓ | 200 ✓ |
| **User** | 302 → `/meeting-notice` | 200 ✓ | 200 ✓ | 200 ✓ |
| **Staff** | 200 ✓ | 200 ✓ | 200 ✓ | 200 ✓ |
| **Operator** | 200 ✓ | 200 ✓ | 200 ✓ | 200 ✓ |
| **Admin** | 200 ✓ | 200 ✓ | 200 ✓ | 200 ✓ |

**Key Points:**
- Unpublished meetings require `VOTING_VIEW_RESULTS` permission (Staff+)
- Unauthorized users are redirected to `/meeting-notice/<meeting_number>`
- All users can view published meetings

### Booking (`/booking`)

| Role | Unpublished | Not Started | Running | Finished |
|------|-------------|-------------|---------|----------|
| **Guest** | 302 → `/login` | 302 → `/login` | 302 → `/login` | 302 → `/login` |
| **User** | 302 → `/meeting-notice` | 200 ✓ | 200 ✓ | 200 ✓ |
| **Staff** | 200 ✓ | 200 ✓ | 200 ✓ | 200 ✓ |
| **Operator** | 200 ✓ | 200 ✓ | 200 ✓ | 200 ✓ |
| **Admin** | 200 ✓ | 200 ✓ | 200 ✓ | 200 ✓ |

**Key Points:**
- Booking requires authentication (`@login_required`)
- Unpublished meetings require `VOTING_VIEW_RESULTS` permission (Staff+)
- Users can book their own roles with `BOOKING_BOOK_OWN` permission
- Operators/Admins can assign any role with `BOOKING_ASSIGN_ALL` permission

### Voting (`/voting`)

| Role | Unpublished | Not Started | Running | Finished |
|------|-------------|-------------|---------|----------|
| **Guest** | 302 → `/meeting-notice` | 302 → `/meeting-notice` | 200 ✓ | 302 → `/agenda` |
| **User** | 302 → `/meeting-notice` | 302 → `/meeting-notice` | 200 ✓ | 302 → `/agenda` |
| **Staff** | 302 | 302 | 200 ✓ | 200 ✓ |
| **Operator** | 302 | 302 | 200 ✓ | 200 ✓ |
| **Admin** | 302 | 302 | 200 ✓ | 200 ✓ |

**Key Points:**
- Voting is only available for `running` meetings (all users)
- Unpublished/Not Started meetings require `VOTING_TRACK_PROGRESS` permission (Operator+)
- Finished meetings require `VOTING_VIEW_RESULTS` permission (Staff+) to view results
- Guests and Users are redirected to agenda (where they see thank-you message)

### Other Resources

| Resource | Guest | User | Staff | Operator | Admin |
|----------|-------|------|-------|----------|-------|
| **Pathway Library** | 200 ✓ | 200 ✓ | 200 ✓ | 200 ✓ | 200 ✓ |
| **Lucky Draw** | 302 | 302 | 200 ✓ | 200 ✓ | 200 ✓ |
| **Roster** | 302 | 302 | 200 ✓ | 200 ✓ | 200 ✓ |
| **Contacts** | 302 | 302 | 200 ✓ | 200 ✓ | 200 ✓ |
| **Speech Logs** | 302 | 200 ✓ | 200 ✓ | 200 ✓ | 200 ✓ |
| **Settings** | 302 | 302 | 302 | 200 ✓ | 200 ✓ |
| **Users** | 302 | 302 | 302 | 302 | 200 ✓ |

## Permission Mappings

### Core Permissions

| Permission | Guest | User | Staff | Operator | Admin |
|------------|-------|------|-------|----------|-------|
| `AGENDA_VIEW` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `AGENDA_EDIT` | ✗ | ✗ | ✗ | ✗ | ✓ |
| `BOOKING_BOOK_OWN` | ✗ | ✓ | ✗ | ✗ | ✓ |
| `BOOKING_ASSIGN_ALL` | ✗ | ✗ | ✗ | ✓ | ✓ |
| `VOTING_VIEW_RESULTS` | ✗ | ✗ | ✓ | ✓ | ✓ |
| `VOTING_TRACK_PROGRESS` | ✗ | ✗ | ✗ | ✓ | ✓ |
| `ROSTER_VIEW` | ✗ | ✗ | ✓ | ✓ | ✓ |
| `ROSTER_EDIT` | ✗ | ✗ | ✗ | ✓ | ✓ |
| `CONTACT_BOOK_VIEW` | ✗ | ✗ | ✓ | ✓ | ✓ |
| `CONTACT_BOOK_EDIT` | ✗ | ✗ | ✗ | ✗ | ✓ |
| `SPEECH_LOGS_VIEW_ALL` | ✗ | ✗ | ✓ | ✓ | ✓ |
| `SETTINGS_VIEW_ALL` | ✗ | ✗ | ✗ | ✓ | ✓ |
| `LUCKY_DRAW_VIEW` | ✗ | ✗ | ✓ | ✓ | ✓ |
| `LUCKY_DRAW_EDIT` | ✗ | ✗ | ✗ | ✓ | ✓ |
| `PATHWAY_LIB_VIEW` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `PATHWAY_LIB_EDIT` | ✗ | ✗ | ✗ | ✓ | ✓ |

## Special Behaviors

### Unauthorized Meeting Access

When an unauthorized user (Guest or User) tries to access a meeting they shouldn't (e.g., unpublished or not started):

1. **Agenda Route**: Redirects to `/meeting-notice/<meeting_number>`
2. **Booking Route**: Redirects to `/meeting-notice/<meeting_number>` (after login)
3. **Voting Route**: Redirects to `/meeting-notice/<meeting_number>`

The `/meeting-notice` page displays:
- Meeting number
- Real meeting status (e.g., "Meeting #960 is unpublished.")
- Illustration image
- No meeting selector or navigation

### Default Meeting Selection

The system automatically selects a default meeting based on priority:

1. **Running** meeting (highest priority)
2. **Lowest numbered** unfinished meeting (`not started` or `unpublished`)
3. If no unfinished meetings exist, returns `None`

**Note:** Unpublished meetings are included in default selection regardless of user permissions. Access control is enforced at the route level.

### Meeting Date Validation

When creating a new meeting:
- The meeting date **cannot be earlier** than the most recent meeting's date
- This ensures chronological order is maintained
- Validation occurs in `_validate_meeting_form_data()`

## Implementation Notes

### Route Decorators

- `@login_required`: Requires authentication, redirects to `/login` if not authenticated
- `@is_authorized(permission)`: Checks if user has specific permission, redirects to `/` if not

### Access Control Flow

```
Request → Route Decorator Check → Meeting Status Check → Permission Check → Response
```

1. **Route Decorator**: Checks authentication requirements
2. **Meeting Status**: Determines if meeting is accessible based on status
3. **Permission Check**: Validates user has required permissions
4. **Response**: Returns 200 (success), 302 (redirect), or 403 (forbidden)

## Testing

Access control is validated through:
- `tests/test_access_matrix.py` - Comprehensive matrix testing
- `tests/test_route_access.py` - Route-specific access tests
- `tests/test_permission_system.py` - Permission system tests

Run tests with:
```bash
pytest tests/test_access_matrix.py -v
pytest tests/test_route_access.py -v
```

## Change Log

### 2026-01-15
- **Changed**: Unpublished meetings now redirect to `/meeting-notice` instead of showing masked view
- **Changed**: Default meeting selection now includes unpublished meetings for all users
- **Changed**: Renamed `meeting-not-started` to `meeting-notice` and added real meeting status display
- **Added**: Meeting date validation to prevent creating meetings with earlier dates
- **Updated**: All tests to reflect new redirect behavior
