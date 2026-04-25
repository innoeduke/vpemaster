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

---

## Detailed Task Instructions

### Task 1: Create a New User and Assign a Role

**Route**: `GET/POST /users/new`

**Steps**:
1. Navigate to **Users** → **Create New User**
2. Fill in the required fields:
   - **First Name**: Member's first name
   - **Last Name**: Member's last name
   - **Email**: Login email (must be unique)
   - **Member ID**: Toastmasters official member ID (optional but recommended)
   - **Phone**: Contact phone number (optional)
3. Select the appropriate **Role** from the dropdown
4. Click **Create User**

**Available Roles**:

| Role | Description | Permissions |
|------|-------------|-------------|
| **Member** | Regular club member | View agenda, book roles, log speeches, vote |
| **Officer** | Club officer with specific responsibilities | Above + manage meeting roles, view reports |
| **Admin** | Full system administrator | All features including user management, settings, permissions |
| **Super Admin** | System-wide admin for multi-club management | Above + create/delete clubs, manage all clubs |

**Role Hierarchy**: Super Admin > Admin > Officer > Member

---

### Task 2: Add & Update a Contact

**Adding a New Contact**:
**Route**: `GET/POST /contacts/new`

1. Navigate to **Contacts** → **Add Contact**
2. Fill in contact details:
   - **Name**: Full name
   - **Email**: Email address
   - **Phone**: Phone number (optional)
   - **Type**: Select **Member** or **Guest**
   - **Club**: Select the club this contact belongs to
   - **Notes**: Any additional notes (optional)
3. Click **Save Contact**

**Updating an Existing Contact**:
**Route**: `GET/POST /contacts/<contact_id>/edit`

1. Navigate to **Contacts** → select the contact
2. Click **Edit** button
3. Modify the desired fields
4. Click **Update Contact** to save changes

**Guest Check-in**:
When a guest attends a meeting:
1. Navigate to the meeting session
2. Find the guest in contacts or create new
3. Mark attendance for that meeting

---

### Task 3: Build the Agenda of a New Meeting

**Route**: `GET/POST /agenda`

**Steps**:
1. Navigate to **Meetings** → **New Agenda** (or `/agenda/new`)
2. Select the **Club** from the dropdown
3. Set the **Meeting Date** and **Start Time**
4. Configure **Agenda Items**:
   - Click **Add Segment** to add agenda sections
   - Each segment has: Title, Duration (minutes), Items
   - Add items to each segment: Prepared Speeches, Evaluations, Table Topics, etc.
5. **Auto-Calculate**: System automatically calculates end times based on durations
6. Review and adjust individual role assignments
7. Click **Save Agenda** or **Publish Agenda**

**Agenda Templates**:
- Use saved templates for recurring meeting formats
- Templates can be created from existing agendas

**Agenda Time Calculation**:
| Item | Typical Duration |
|------|-----------------|
| Prepared Speech | 5-7 minutes |
| Evaluation | 2-3 minutes |
| Table Topic | 1-2 minutes |
| General Evaluator Report | 3-5 minutes |

---

### Task 4: Create a New Session

**Route**: `GET/POST /sessions/new`

A session represents a single club meeting.

**Steps**:
1. Navigate to **Sessions** → **Create New Session**
2. Fill in session details:
   - **Session Title**: e.g., "Weekly Meeting #123"
   - **Club**: Select the club
   - **Meeting Date**: Date of the meeting
   - **Start Time**: When the meeting begins
   - **Location**: Meeting venue (Physical/Virtual/Hybrid)
   - **Agenda**: Select or create an agenda for this session
3. Configure **Session Options**:
   - Enable/disable voting
   - Enable/disable speech logging
   - Set meeting status: Planned / In Progress / Completed
4. Click **Create Session**

**Session Status Workflow**:
- **Planned**: Agenda built, roles assigned
- **In Progress**: Meeting is happening, live voting active
- **Completed**: Meeting finished, final reports generated

**Post-Meeting Actions**:
After a session:
1. Mark session as **Completed**
2. Finalize attendance records
3. Generate meeting summary
4. Export reports if needed

---

### Task 5: Add a Prepared Speech

**Route**: `GET/POST /speeches/new` or via Agenda Builder

**Steps**:
1. Navigate to **Speeches** → **Log New Speech**
2. Select the **Member** who gave the speech
3. Fill in speech details:
   - **Speech Title**: Title of the speech
   - **Project Number**: Pathways project number (e.g., DL1, DL2, PC1)
   - **Pathway Level**: Current level of the speaker
   - **Meeting Date**: Date of the speech
   - **Duration (minutes)**: How long the speech was
   - **Evaluation Received**: Select evaluator or mark "No Evaluation"
4. Add **Evaluation Notes** (optional):
   - Evaluator's written feedback
   - Awards received (if any)
5. Click **Save Speech**

**Via Agenda Builder**:
When building an agenda:
1. In the agenda builder, click **Add Prepared Speech**
2. Select the **Speaker** from the member dropdown
3. Auto-populates the speaker's next required project if available
4. Set speech duration
5. Speaker will be automatically assigned to that agenda slot

**Pathways Project Codes**:
| Code | Project Type |
|------|-------------|
| DL1-DL5 | Dynamic Leadership |
| PC1-PC5 | Persuasive Communication |
| EC1-EC5 | Effective Coaching |
| SR1-SR5 | Strategic Relationships |
| CR1-CR5 | Conflict Resolution |
| DR1-DR5 | Directing |
| MS1-MS5 | Managing Leadership |

---

### Task 6: Add an Individual Evaluator

**Route**: `GET/POST /evaluations/new` or via Agenda Builder

**Steps**:
1. Navigate to **Evaluations** → **Assign Evaluator**
2. Select the **Meeting/Session**
3. Select the **Speaker** being evaluated
4. Select the **Evaluator** (must be a club member)
5. Configure evaluation details:
   - **Role**: General Evaluator or Speech Evaluator
   - **Is Substitution**: Mark if this is a last-minute replacement
6. Click **Assign Evaluator**

**Via Agenda Builder**:
1. In the agenda, find the speech slot
2. Click **Assign Evaluator**
3. Select the evaluator from the dropdown
4. The evaluator is automatically linked to that speech

**General Evaluator Role**:
The General Evaluator oversees all evaluations during a meeting:
- Introduces each evaluator
- Provides overall feedback on the meeting
- Typically assigned in the agenda builder as a separate role

**Evaluation Best Practices**:
- Assign evaluators who have completed relevant projects
- Consider pairing new members with experienced evaluators
- Ensure evaluators confirm availability before finalizing

---

### Task 7: Add a Table Topic Speaker

**Route**: `GET/POST /table-topics/new` or via Agenda Builder

**Table Topics** are impromptu speeches given by members who volunteer.

**Steps**:
1. Navigate to **Table Topics** → **Assign Speaker**
2. Select the **Meeting/Session**
3. Select the **Member** giving the table topic
4. Optionally set a **Topic Theme** or specific question
5. Set **Time Limit** (default: 1-2 minutes)
6. Click **Assign**

**Via Agenda Builder**:
1. In the agenda, add a **Table Topics** segment
2. Click **Add Table Topic Speaker**
3. Select member from the list
4. Add as many speakers as needed (recommended: 3-5)
5. System will track attendance for each speaker

**TT Speaker Management**:
- Mark speakers as **Completed** or **No Show**
- Add notes for speakers who went off-topic or exceeded time
- Award "Best Table Topic" during voting if enabled

**Common Table Topic Themes**:
- Pick-a-topic random selection
- Theme-based (e.g., "Childhood Memories")
- Word Association
- "What if..." scenarios

---

### Task 8: Update Club Info & ExComM Members

**Updating Club Information**:
**Route**: `GET/POST /clubs/<club_id>/edit`

1. Navigate to **Clubs** → select club → **Edit**
2. Update any of the following fields:
   - **Club Name**: Official club name
   - **Club Number**: Toastmasters assigned number
   - **Short Name**: Abbreviated name for display
   - **District/Division/Area**: Geographic assignment
   - **Meeting Schedule**: Day and time
   - **Meeting Location**: Venue address or virtual link
   - **Club Email/Phone**: Contact information
   - **Website/Social Media**: Online presence
   - **Logo URL**: Club logo for branding
3. Click **Save Changes**

**Managing ExComM Members**:
**Route**: `GET/POST /clubs/<club_id>/excomm`

1. Navigate to **Clubs** → select club → **ExComM**
2. For each officer position:
   - Select the **Member** from dropdown
   - Set **Term Start Date**
   - Set **Term End Date** (typically 6-12 months)
3. Click **Update ExComM** to save

**ExComM Positions**:

| Position | Abbreviation | Responsibilities |
|---------|-------------|-----------------|
| President | - | Club leadership, meeting facilitation, ExComM coordination |
| Vice President Education | VPE | Speech/evaluation tracking, meeting quality, mentor matching |
| Vice President Membership | VPM | New member recruitment, guest follow-up, membership growth |
| Vice President Public Relations | VPPR | Club promotion, social media, external communications |
| Secretary | - | Meeting minutes, records, correspondence |
| Treasurer | - | Finances, dues collection, budget management |
| Sergeant at Arms | SAA | Meeting logistics, room setup, guest welcome |
| Immediate Past President | - | ExComM advisor, continuity, mentorship |

**Officer History**:
- All past officers are tracked with their term dates
- Useful for generating officer certificates
- Maintains institutional memory

---

### Task 9: Add a Roster Entry

**Route**: `GET/POST /roster/new`

The roster tracks member participation and attendance over time.

**Steps**:
1. Navigate to **Roster** → **Add Entry**
2. Select the **Club** and **Session/Meeting**
3. Select the **Member** being rostered
4. Set **Attendance Status**:
   - **Present**: Attended the meeting
   - **Absent**: Did not attend
   - **Excused**: Absent with valid reason
5. Assign **Roles Filled** (can select multiple):
   - Speaker
   - Evaluator
   - Table Topic Speaker
   - General Evaluator
   - Toastmaster
   - Topics Master
   - Ah-Counter
   - Grammarian
   - Timer
   - Quiz Master
6. Add **Notes** if needed (e.g., "First meeting as guest")
7. Click **Add Roster Entry**

**Bulk Roster Entry**:
**Route**: `POST /roster/bulk-update`

For quick attendance marking:
1. Navigate to **Roster** → **Bulk Update**
2. Select the meeting
3. Check/uncheck attendance for each member
4. Assign roles for those who participated
5. Click **Save All**

**Roster Reports**:
- Member attendance percentage
- Role completion counts
- Guest attendance tracking
- Export to CSV/Excel

**Maintenance**:
- Remove duplicate entries if attendance was marked twice
- Update entries within 7 days of meeting for accuracy
- Archive old roster data seasonally

---


---

### Task 10: Add a Ticket Type

VPEMaster includes a ticketing system for tracking club issues, maintenance requests, and member support needs.

**Route**: `GET/POST /tickets/new-type` or `/tickets/types`

**Steps**:
1. Navigate to **Tickets** → **Manage Types** → **Add New Type**
2. Fill in ticket type details:
   - **Type Name**: Descriptive name (e.g., "Room Maintenance", "Member Support", "Event Request")
   - **Description**: Brief explanation of the ticket type
   - **Category**: Group the type under a broader category:
     - Facilities (room, equipment, supplies)
     - Membership (dues, applications, transfers)
     - Events (social events, contests, workshops)
     - Technical (website, voting system, app issues)
     - Administrative (records, reports, compliance)
   - **Priority Level**: Set default priority:
     - Low (general inquiries)
     - Medium (needs attention within a week)
     - High (affects meeting operations)
     - Urgent (blocks current activities)
   - **Default Assignee**: Who typically handles this type (optional)
   - **SLA Response Time**: Target response time (e.g., 24 hours, 3 days)
3. Configure **Workflow Options**:
   - Allow multiple assignees: Yes/No
   - Require approval before closure: Yes/No
   - Auto-close after resolution: Yes/No
4. Click **Create Ticket Type**

**Managing Existing Ticket Types**:
**Route**: `/tickets/types`

- View all ticket types in a list
- Edit a type by clicking the type name
- Toggle active/archived status
- Archived types won't appear in new ticket dropdowns but history is preserved

**Ticket Lifecycle**:
1. **Open**: Ticket created, awaiting assignment
2. **Assigned**: Someone is working on it
3. **In Progress**: Work actively happening
4. **Pending**: Waiting on requester or external input
5. **Resolved**: Issue fixed, awaiting confirmation
6. **Closed**: Confirmed resolved, ticket archived

**Ticket Type Examples**:

| Type Name | Category | Priority | Typical Use |
|-----------|----------|----------|-------------|
| Room Booking | Facilities | Medium | Meeting room issues |
| New Member Inquiry | Membership | Medium | Questions about joining |
| Printer Problem | Facilities | High | Meeting equipment down |
| Contest Registration | Events | Low | Interest in contests |
| Voting System Bug | Technical | Urgent | Can't access voting |
| Dues Payment | Membership | High | Payment issues |

**Ticket Dashboard**:
**Route**: `/tickets`

Shows:
- Open tickets by type
- Tickets approaching SLA deadline (highlighted red)
- My assigned tickets
- Recent activity feed

---

