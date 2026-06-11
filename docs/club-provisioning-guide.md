# Club Provisioning Guide — Hand-off Document

A friendly, step-by-step guide for the new club admin to set up their club in the system. Assumes the club admin will use the web interface (no CLI or file editing required).

---

## Part 1: Information to Collect from the Club Admin

Before logging into the system, gather this information from the new club admin. Most of it is **required**; everything is **needed eventually**, so collect what you can now and schedule follow-ups for the rest.

### A. Club Identity (Required)

| Question | Example | Notes |
|---|---|---|
| What is your **Toastmasters club number**? | `868941` | Must be unique; assigned by Toastmasters International |
| What is your **full club name**? | `Shanghai Leadership Toastmasters Club` | Will appear on all agendas and reports |
| Do you want a **short name or abbreviation** for internal use? | `SLTMC` | Optional; helps with quick reference |
| What **District, Division, and Area** are you in? | `District 85, Division K, Area K1` | Used for the club info banner |

### B. Meeting Logistics (Required)

| Question | Example |
|---|---|
| **What day(s) of the week** do you meet? | `Every Wednesday` |
| What **start time** do you typically use? | `18:55` (entered as HH:MM, 24-hour format) |
| What is the **meeting address or location** (physical or virtual link)? | `123 Main St, Shanghai` or `https://zoom.us/j/...` |
| Do you have a **club contact phone number**? | `+86 138 0000 0000` |
| What is your **club website** (if any)? | `shanghaitm.org` |

### C. Club Branding (Required for a polished look)

| Question | Example |
|---|---|
| Do you have a **club logo** (PNG, JPG, or WebP)? | Square format works best; will be resized to 500×500 |
| When was your club **chartered (founded)**? | `2010-06-15` (YYYY-MM-DD) |

### D. ExComm Team (Required to finalize the team page)

| Position | Question to Ask | Notes |
|---|---|---|
| **President** | Who is your current club President? (Name, email, member ID if known) | All 8 positions should be filled if possible |
| **VPE** (Vice President Education) | Who is your VPE? | |
| **VPM** (Vice President Membership) | Who is your VPM? | |
| **VPPR** (Vice President Public Relations) | Who is your VPPR? | |
| **Secretary** | Who is your Secretary? | |
| **Treasurer** | Who is your Treasurer? | |
| **SAA** (Sergeant at Arms) | Who is your SAA? | |
| **Immediate Past President** | Who is your Immediate Past President? | |
| **Team name** (optional) | Does your ExComm have a fun team name? | e.g. "Memory Makers" |
| **Term dates** | What is the start and end date of this term? | Toastmasters terms are half-year (H1 = Jul-Dec, H2 = Jan-Jun) |
| **Term code** | What is the term code? (e.g. `26H1` for the first half of 2026) | |

### E. Initial Admin User (Required)

| Question | Example |
|---|---|
| Who will be the **first club admin**? (Name, email) | `Kyle Wei, kyle@example.com` |
| What **username** should they use to log in? | `kylewei` |
| Do you have a **preferred initial password**? | (They can change it after first login) |

### F. Feature Preferences (Optional — can be decided after exploring)

Ask the club admin which of these features they want to enable. You can skip this section and let them decide as they go.

- [ ] **Booking** — Members self-book roles in upcoming meetings?
- [ ] **Voting** — Audience votes for best speaker/evaluator/role-taker during meetings?
- [ ] **Roster** — Track per-meeting attendance?
- [ ] **Calendar** — Calendar view of meetings?
- [ ] **Chatbot / AI Assistant** — Anthropic-powered AI chat for the club? (Requires API key)
- [ ] **Journal / Speech Logs** — Track member speech projects?
- [ ] **Club Directory** — Show your club in the cross-club directory?
- [ ] **Planner** — Help members plan their role history?
- [ ] **Lucky Draw** — Random role picker for Table Topics?
- [ ] **Upload Links** — File collection for the club?
- [ ] **Data / Slides Export** — Export agendas to Excel / PowerPoint?
- [ ] **Self Check-In** — Members check themselves in via QR / link?

### G. Meeting Templates (Optional)

The system comes with two default meeting templates (**Keynote Speech** and **Panel Discussion**). Ask if the club wants to use these or upload custom templates. The full list of available templates:

- Keynote Speech
- Panel Discussion
- Speech Marathon
- Speech Contest
- Debate
- Pecha Kucha
- Gavel Passing
- Club Election

---

## Part 2: Step-by-Step Configuration

After collecting the information above, walk the new club admin through these steps in the web interface.

### Step 1: Log In & Create the Club

1. Open the app and log in as a **SysAdmin** (the developer will provide credentials for the initial setup).
2. Navigate to **Clubs → New Club**.
3. Fill in the required fields:
   - **Club Number** (from A)
   - **Club Name** (from A)
4. Click **Create Club**. The system creates a shell club row and copies default files (logo, slide layouts, the two default agenda templates).

> 💡 **Tip**: The new club starts with all feature modules **disabled** and with no session types or roles. You'll add those in the next steps.

### Step 2: Fill In Club Details

1. Navigate to **About Club** (or **Settings → About**).
2. Fill in:
   - Short name, District/Division/Area (from A)
   - Meeting day, start time, address, phone, website (from B)
   - Founded date (from C)
3. **Upload the club logo**:
   - Click the logo area, select your PNG/JPG/WebP file.
   - The system will resize it to 500×500 and convert to WebP automatically.
4. Click **Save**.

> 💡 **Tip**: The club info banner (Club No. | Area | Division | District | Club Name) is automatically generated from these fields.

### Step 3: Create the First Admin User

> ⚠️ **This step requires SysAdmin access** — coordinate with the developer.

The developer will create the first admin user via the command line, then notify you when the account is ready. You will then:

1. Log in with the credentials provided.
2. Change your password immediately (**Profile → Change Password**).
3. Verify you have ClubAdmin access by navigating to **Settings** (you should see all tabs).

### Step 4: Set Up the ExComm Team

1. Navigate to **Settings → ExComm** tab.
2. Click **Add New Term**:
   - Enter the **term code** (e.g. `26H1`), start date, end date, and optional team name.
3. After saving, you'll see the 8 officer positions. For each, click the dropdown and select the member who fills that role.
4. Save after each assignment.

> 💡 **Tip**: If a member isn't in the list yet, they need to be added first via **Members → Add Member**.

### Step 5: Enable Feature Modules

1. Navigate to **Settings → Permissions** tab.
2. Scroll to **Functional Modules**.
3. Toggle **ON** the modules the club wants (from section F). Core is always on.
4. Click **Save**.

> 💡 **Tip**: You can change these anytime. Start with the essentials (Booking, Voting, Roster) and add more later as the club gets comfortable.

### Step 6: Review and Adjust Permissions (Optional)

1. Still in **Settings → Permissions**, scroll to the **Permission Matrix**.
2. Review the default permissions for each role (SysAdmin, ClubAdmin, Operator, Staff, Member, Guest).
3. Adjust as needed for your club's workflow.
4. Click **Save**.

> 💡 **Tip**: If you want to save the current matrix as your club's permanent default, click **Save as Default**. This writes a snapshot that "Reset to Default" will restore.

### Step 7: Verify Everything Works

Before announcing the system to members, do a quick smoke test:

1. **Create a test meeting**: Go to **Agenda → New**, fill in the details, and create it.
2. **Open the agenda**: Verify the club info banner, meeting title, and date are correct.
3. **Check a module** (if enabled): Try booking a role, or voting, or whatever the club enabled.
4. **Log out and log in as a regular member**: Verify they can see the published agenda and book roles.

---

## Quick Reference: Settings to Configure

A condensed checklist of every setting and where to configure it:

### Club-Level Settings (About Club page)

- [ ] Club number, name, short name
- [ ] District, Division, Area
- [ ] Meeting day, start time
- [ ] Address, phone, website
- [ ] Logo upload
- [ ] Founded date

### ExComm (Settings → ExComm)

- [ ] Current term (code, dates, team name)
- [ ] 8 officer assignments (President, VPE, VPM, VPPR, Secretary, Treasurer, SAA, Immediate Past President)

### Feature Modules (Settings → Permissions → Functional Modules)

- [ ] Booking
- [ ] Voting
- [ ] Roster
- [ ] Calendar
- [ ] Chatbot
- [ ] Journal / Speech Logs
- [ ] Club Directory
- [ ] Planner
- [ ] Lucky Draw
- [ ] Upload Links
- [ ] Data / Slides Export
- [ ] Self Check-In

### Permissions (Settings → Permissions → Permission Matrix)

- [ ] Review defaults for all 6 built-in roles
- [ ] Adjust as needed
- [ ] (Optional) Save as Default

### Meeting Templates (Settings → Sessions / Settings → Roles)

- [ ] Review default session types (SAA Session, President Session, Toastmaster Session, etc.)
- [ ] Review default meeting roles (President, VPE, etc.)
- [ ] (Optional) Upload custom meeting templates (Keynote Speech, Panel Discussion, etc.)

---

## Common Pitfalls

- **Logo not square**: A non-square logo will be letterboxed or cropped. Ask for a square version if possible.
- **Club number already exists**: Each club number must be unique across the entire system. Verify with Toastmasters before creating.
- **ExComm term dates**: Toastmasters terms are half-year. H1 = July–December, H2 = January–June. The term code format is `<YY>H<1|2>` (e.g. `26H1`).
- **Module toggles are global per club**: Enabling "Voting" for the club doesn't enable it for every meeting — each meeting must be published and started separately.
- **Permissions matrix is per-club**: Changes here only affect this club, not other clubs in the system.

---

## Verification Checklist

After completing all steps, verify:

- [ ] The new club appears in the club list.
- [ ] The club admin can log in and sees the Settings page.
- [ ] The ExComm team is visible on the About Club page.
- [ ] At least one feature module is enabled and functional.
- [ ] A test meeting can be created and viewed.
- [ ] A regular member can log in and see the published agenda.

---

## Support

If you get stuck, contact the developer. Common issues:

- **"Permission denied" errors**: The user may not have the right role. Check Settings → Members.
- **"Session type not found"**: The club may not have session types seeded. The developer can run `flask import-data` to bulk-load them.
- **Logo won't upload**: File may be too large (>2MB) or wrong format. Try a smaller PNG.
