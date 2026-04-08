# VPEMaster Club Admin User Guide

VPEMaster is a comprehensive Toastmasters club management system supporting multi-club operations, Pathways tracking, meeting management, and member administration.

---

## Getting Started

### Accessing the System
- URL: `http://localhost:5000` (local development) or your configured server URL
- Login required for all admin functions
- Contact your system administrator if you need an account

### Initial Setup
1. **Configure Club Settings**: Navigate to Settings → Club Configuration
2. **Add Club Information**: Set club name, number, meeting schedule, and location
3. **Create Member Accounts**: Add members manually or via bulk import
4. **Set Up Officer Roles**: Assign ExComM members to their roles

---

## Club Management

### Creating a New Club
**Route**: `GET/POST /clubs/new`

1. Navigate to Clubs → Create New Club
2. Fill in required fields:
   - Club Number (unique identifier)
   - Club Name
   - District/Division/Area
   - Meeting Date and Time
   - Club Address
3. Click "Create Club"

### Editing Club Details
**Route**: `GET/POST /clubs/<club_id>/edit`

Access via Clubs → List → Edit icon for your club.

Editable fields include:
- Club name and short name
- Meeting schedule
- Contact information
- District/Division/Area assignments
- Logo URL

### Club Context Switching
For multi-club admins:
- Dropdown in header to switch between clubs
- All operations are scoped to selected club context

---

## Member Management

### Adding Members
**Route**: `GET/POST /users/new`

Fields:
- First Name, Last Name
- Email (used for login)
- Member ID (Toastmasters official ID)
- Role (Member, Officer, Admin)

### Bulk Import
**Route**: `POST /users/bulk-import`

CSV format with columns:
```
first_name,last_name,email,member_id,phone
```

### User List
**Route**: `/users`

Features:
- Search by name/email
- Filter by role
- View member profile
- Edit/Delete users

### Join Requests
**Route**: `GET/POST /users/join-request` (member facing)
**Route**: `POST /users/respond-join` (admin)

Members can request to join; admins approve/reject.

---

## ExComM / Officer Management

### Officer Roles
Standard Toastmasters officer positions:
- President
- Vice President Education (VPE)
- Vice President Membership (VPM)
- Vice President Public Relations (VPPR)
- Secretary
- Treasurer
- Sergeant at Arms (SAA)
- Immediate Past President

### Managing Officers
**Route**: `GET/POST /clubs/<club_id>/edit`

Access ExComM section to:
- Assign officers to roles
- Set term start/end dates
- View officer history

### Officer History
Track past officers with start/end dates for each role.

---

## Meeting Management

### Agenda Builder
**Route**: `/agenda`

Features:
- Dynamic agenda creation with automatic time calculations
- Template-based agenda generation
- Real-time role booking
- Waitlist management for popular roles

### Role Booking
**Route**: `/booking`

Members can:
- Book meeting roles (Speaker, Evaluator, Table Topic, etc.)
- Join waitlists for oversubscribed roles
- Officers approve/remove bookings

### Voting
**Route**: `/voting` (during meeting)

Live voting for:
- Best Speaker
- Best Evaluator
- Best Table Topic
- Other custom awards

Results can be exported.

---

## Pathways & Progress Tracking

### Speech Logs
**Route**: `/speech-logs`

Track member speeches:
- Speech title and project
- Date completed
- Evaluation
- Manual override for manually-logged speeches

### Path Progression Matrix
**Route**: `/speech-logs/matrix/<user_id>`

Visual representation of:
- Completed projects
- Current level
- Next recommended project
- Missing achievements

### Achievements
**Route**: `/achievements`

Achievement types:
- Level completion
- Path completion
- Program completion (DTM)

---

## Contacts Management

### Contact List
**Route**: `/contacts`

Features:
- All club members and guests
- Search and filter
- View contact details
- Edit/Delete contacts

### Guest Management
Track guests separately from members:
- Name and email
- Type (Guest/Member)
- Events attended

---

## Settings & Configuration

### General Settings
**Route**: `/settings`

Options:
- Theme selection (including seasonal themes)
- Email notifications
- Export preferences

### Permission Management
**Route**: `/permissions`

Admin-only:
- View role permissions
- Assign/revoke permissions
- Permission audit log

### Impersonation
Admins can impersonate users to:
- View member-facing pages
- Debug issues
- All actions logged

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Can't login | Check email/password; reset if needed |
| Missing member data | Verify user profile completion |
| Agenda not calculating times | Check meeting duration settings |
| Role booking failed | Check if role has available slots |
| Export not working | Verify export service is running |

### Logs
Check application logs at:
- Development: Console output
- Production: `/var/log/vpemaster/`

### Database
SQLite database: `app/toastmasters.db`

For migrations:
```bash
flask db upgrade
```

---

## Route Reference

| Route | Description |
|-------|-------------|
| `/` | Home/Dashboard |
| `/clubs` | List clubs |
| `/clubs/new` | Create club |
| `/clubs/<id>/edit` | Edit club |
| `/users` | List users |
| `/users/new` | Create user |
| `/users/bulk-import` | Bulk import |
| `/users/join-request` | Join request |
| `/agenda` | Agenda builder |
| `/booking` | Role booking |
| `/voting` | Live voting |
| `/speech-logs` | Speech logs |
| `/achievements` | Achievements |
| `/contacts` | Contacts |
| `/settings` | Settings |
| `/permissions` | Permissions |

---

## Support

For technical issues, contact the VPEMaster development team.
