# Memory Maker — VPE Tutorial: Managing a Full Meeting Cycle

> **Audience:** Vice President Education (VPE) and any officer who owns the meeting content. No coding background assumed.
> **Goal:** Walk through every screen and action a VPE touches in Memory Maker, from a week before the meeting to the day after.
> **Last updated:** 2026-06-22

Memory Maker is the club's web app for planning, running, and recording Toastmasters meetings. As VPE, you are the primary owner of the meeting's *content* — the agenda, the role assignments, the prepared speeches, and the Pathways tracking. The SAA owns the *room* (check-in, voting tallying, lucky draw). This tutorial stays on the VPE side, with notes where the two roles overlap.

The full cycle has four phases:

1. **Phase 1 — Pre-Meeting Planning** (T-7 days to T-1 day): create the meeting, build the agenda, open booking.
2. **Phase 2 — Reception** (T-0, 6:30 PM): the SAA handles check-in, but you should confirm the meeting is ready to publish.
3. **Phase 3 — Live Meeting** (T-0, 7:00–9:00 PM): publish → start → react to in-meeting changes → stop.
4. **Phase 4 — Wrap-Up & Records** (T+0 to T+1): confirm speech logs, Pathways progress, voting results, archive the meeting.

---

## Phase 1 — Pre-Meeting Planning

This is where you do the bulk of your work. The goal is to leave the club with a published meeting, a complete agenda, and roles booked — so that on the night, the only thing left is to press **Start**.

### 1.1 Open the Agenda page

In the top navigation bar, click **Agenda**. This is the home base for everything meeting-related. The page shows a meeting selector at the top and a status group showing the current meeting's status (Unpublished / Not Started / Running / Finished / Cancelled).

If the meeting you want does not exist yet, you'll create it (see 1.2). If it exists but is still **Unpublished**, you're in good shape to keep editing.

### 1.2 Create the meeting from a template

1. On the Agenda page, click **New** (the action is in the top-right area of the page).
2. Fill in the form:
   - **Meeting Date** — the date the meeting will be held. Memory Maker flags suspicious dates (e.g. far in the past) and asks you to confirm.
   - **Meeting Number** — a positive integer unique within your club. Used to renumber meetings if a date changes.
   - **Meeting Title / Theme** — the theme that ties the meeting together (e.g. "Storytelling Night").
   - **Subtitle** (optional) — secondary line shown under the title.
   - **Meeting Type** — e.g. Regular, Special, Joint Meeting.
   - **Media URL** — a link to the recording of the meeting (leave blank before the meeting; add it after).
   - **Template File** — pick a session template (e.g. "Standard Club Meeting"). This determines the default set of agenda items.
3. Click **Save**. Memory Maker creates the meeting record and generates the default agenda items (one row per session slot) from the template.

> **Tip:** If your club only has one template, you can ignore the field — it defaults to that template. The **New** button is only visible to officers who have permission to create meetings; if you don't see it, ask a ClubAdmin.

### 1.3 Build the agenda

The Agenda page shows the session list as a table with columns for **Start Time**, **Session**, **Owner**, **Project**, and status flags. Each row is editable inline.

Common edits:

- **Add or remove a session** — use the row controls at the bottom of the table. Removing a session is safe as long as no one has booked it.
- **Reorder sessions** — drag the row handle, or use the up/down arrows in the row.
- **Edit a session's start time** — click the time cell and type the new value (24-hour `HH:MM`). Memory Maker warns you if two sessions overlap.
- **Set the Word of the Day (WOD)** — the WOD field is at the top of the editor; the value you set is shown on slides and used by the Memory Maker in the live meeting.
- **Set the GE Style** — the **GE Style** dropdown at the top of the editor controls the General Evaluator's report style. Pick the one your club uses.
- **Edit meeting-level fields** (Title, Subtitle, Type, WOD, Media URL, Meeting Number) — these are in the meeting header section of the editor. Click **Save** to persist your changes.

> **Tip:** A red badge in the table indicates a validation problem (overlap, missing owner for a required role, missing project on a prepared-speech slot). Resolve these before publishing.

### 1.4 Add project info for prepared speeches

Prepared speech sessions are flagged with a project-related indicator. For each such session, you must attach a **Pathways project** so the speech counts toward the speaker's level.

1. Click the project cell of the row.
2. Pick the speaker's pathway (e.g. *Dynamic Leadership*).
3. Pick the project (e.g. *Level 1 — Ice Breaker*).
4. Add an optional title.

If the speaker hasn't told you their project, ask them — the VPE should not guess, because the wrong project will pollute their Pathways record. If the speaker is undecided, you can leave it and update it before the meeting is **Started**.

### 1.5 Open role booking

Once the agenda looks right:

1. Click **Publish** in the status group. Memory Maker asks for confirmation: *"Publishing opens booking roles and speeches to all members. Please make sure the meeting theme and structure are finalized before publishing."*
2. Confirm. The meeting status changes from **Unpublished** to **Not Started**.

The meeting is now visible to all members on the **Booking** page. Members can self-book roles; the system maintains a waitlist automatically when a slot is full.

> **Note:** Once published, the **Meeting Number**, **Title**, **Subtitle**, **Type**, and **WOD** can still be edited, but the session structure is harder to change — if you need to add or remove sessions after publishing, do it before the meeting is **Started**.

### 1.6 Book or assign roles

Two paths exist for role assignment:

- **Member self-booking (default):** Members open the **Booking** page, pick a meeting, and click a slot. The system supports waitlists — a full slot shows a "Join Waitlist" button instead of "Book".
- **Officer assignment (you):** On the Agenda page, click the owner cell of a session and pick a contact. Use this to backfill empty slots 24–48 hours before the meeting, and to assign evaluators to specific speeches.

If a member is on the waitlist and the slot opens, the next person in line is auto-promoted when the current owner cancels. If you manually reassign, the previous owner is dropped without notifying them — tell them out-of-band.

> **Tip:** Keep the **Planner** page in mind here. Members use the Planner to track which projects they want to deliver in upcoming meetings. As VPE, you don't manage Planner entries, but reading the Planner 1–2 days before the meeting helps you see which members plan to take which slot — useful when matching projects to speakers.

### 1.7 Generate slides

From the Agenda page, click **Slides** (or use the Export → PowerPoint action). Memory Maker generates a `.pptx` with the agenda, WOD, theme, and speaker/project info. Review the file — if you have time, do a dry run of the slide transitions, especially around the Timer / Ballot counter.

### 1.8 The day before the meeting

Run through this checklist:

- [ ] Agenda has no red validation badges.
- [ ] Every prepared speech has a Pathways project assigned.
- [ ] Every required role has an owner (or is intentionally left empty — the TME will fill in a substitute on the night).
- [ ] WOD is set and the Word of the Day speaker knows the definition.
- [ ] Slides have been generated and saved to the laptop.
- [ ] The SAA has confirmed they will publish/handle voting on the night (or you will).

If all of the above are green, you are ready for Phase 3.

---

## Phase 2 — Reception (6:30 PM)

The SAA owns this phase. As VPE, your only job is to **be reachable** and to **not publish/start the meeting until the SAA is ready**. See `SAA_MemMaker_User_Manual.md` for the SAA's full checklist.

The one thing you might do here: if the SAA asks you to add a last-minute member to the roster, or to add a table topic speaker to the agenda, do it from the Agenda page — these edits are allowed up to and during the live meeting.

---

## Phase 3 — Live Meeting (7:00 PM – 9:00 PM)

The agenda is on the projector. The SAA is at the door. You're at the laptop. The status button in the Agenda page status group is your only control surface for the meeting lifecycle.

### 3.1 Publish (if not already done)

If you skipped 1.5 because the agenda wasn't final, do it now: click **Publish** in the status group. The button reads "Publish" while the meeting is Unpublished; clicking it moves the meeting to Not Started.

> **Heads up:** Once you publish, members can book or cancel roles in real time. If you have to make a structural change (add/remove sessions), do it before publishing.

### 3.2 Start the meeting

About 5 minutes before the meeting is called to order (typically 6:55 PM):

1. Open the **Agenda** page and select the meeting.
2. Click **Start**. Memory Maker records the start time and changes the meeting status from Not Started to Running.
3. Voting is now enabled. Members can submit ballots from the **Voting** page; the SAA monitors the live count from the same page with the admin toggle.

### 3.3 React to in-meeting changes

During the meeting you'll get requests like:

- *"Can you add John as the Table Topics Speaker #2?"* — Click the owner cell of the relevant session and pick John. Works for Running meetings.
- *"Sarah can't make it, swap her out for Mike for the Ice Breaker."* — Click the owner cell, clear Sarah, pick Mike. The system updates without a page reload.
- *"Add a Table Topics session on the fly."* — Use the **Add Session** control. The new row drops in at the end; reorder by drag if you need it earlier.
- *"I forgot to assign an evaluator."* — Same as the owner-edit flow. The evaluator is just another owner of an evaluator-type session.

> **Tip:** All of these edits go through the Agenda editor's save flow. If you see a red toast at the top of the page, the change was rejected — read the message, fix the data, and retry.

### 3.4 End the meeting

When the General Evaluator wraps up (typically 9:00 PM):

1. Click **Stop** in the status group. Memory Maker will automatically:
   - Change the meeting status to **Finished**.
   - Tally the votes and record the winners.
   - Clear all waitlist entries for this meeting.
   - Update each Planner entry: items you booked are now marked complete, and any waitlisted items are marked obsolete. Drafts stay as drafts.
   - Mark all projects on this meeting as complete, and update each speaker's member record.
2. Voting closes. The SAA can now read the final results on the **Voting** page and run the lucky draw from the **Lucky Draw** page.

> **Heads up:** Once you click **Stop**, the meeting is sealed. You cannot re-open it. If you clicked Stop by accident, contact a ClubAdmin — the only path back is to clone the meeting or restore from backup.

---

## Phase 4 — Wrap-Up & Records (T+0 to T+1)

The meeting is over. The SAA is packing up. You have a few quiet minutes to make sure the records are clean.

### 4.1 Confirm voting results

Open the **Voting** page (or **Voting → NPS** for the NPS view). You should see:

- Final tallies and award winners.
- The NPS score, if your club tracks it.
- The **SAA's lucky-draw verification list** (used to confirm the right people got the right prizes — see SAA manual).

If a winner looks wrong, do **not** edit the ballot record directly. Instead, file an issue from the **Issues** page so the audit trail is preserved.

### 4.2 Update the Media URL

Back on the **Agenda** page, edit the **Media URL** field in the meeting header and save. This attaches the meeting recording to the meeting record — members can find it later from their planner or the meeting archive.

### 4.3 Review the Speech Logs

Open **Contacts → Members**, then click each speaker who delivered a prepared speech. Confirm:

- The project is correctly recorded.
- The level/Pathways progression is correct.

Memory Maker auto-completes projects when the meeting is finished, so usually this is a sanity check. If something looks off (e.g. a speech slot was changed mid-meeting and the wrong project got completed), use the **Speech Logs** page to correct it.

### 4.4 Pathways progress

Open the **Pathways** page and verify each speaker's pathway. Because finishing the meeting auto-syncs each speaker's member record, you should see the level progress increment automatically. If it didn't, the most common cause is the project on the session was left as the generic placeholder — change it to the real project and re-save, which re-runs the level-progress sync.

### 4.5 Achievements

If your club uses the achievements module, open the **Achievements** page and review whether any new badges were earned this meeting (e.g. "First Ice Breaker", "Best Table Topics"). Award them through the Achievements page. This is purely optional but members love it.

### 4.6 Archive or delete the meeting

The status group on the Agenda page now shows **Delete** instead of **Stop**. Two options:

- **Leave the meeting as-is.** It shows in the archive, voting results are preserved, the speech log is preserved. This is the default and what most clubs do.
- **Delete the meeting.** Requires the Meeting Create permission. Deletion is permanent — votes, roster, waitlist, planner entries, and session records all go with it. Only do this if you created the meeting by mistake and it has no real data.

> **Heads up:** The **Delete** button is also how you remove a meeting that was a duplicate or had a wrong date. There is no undo.

### 4.7 Plan ahead

If this meeting set a precedent (new session order, new template, new award category), update the **template** and the **settings** so the next meeting is easier to build. See the Template Manager docs and **Settings → Sessions** for the configuration surfaces.

---

## Quick Reference: Status Flow

```
Unpublished  ──[Publish]──▶  Not Started  ──[Start]──▶  Running  ──[Stop]──▶  Finished
     │                            │                        │                       │
     │                            ▼                        ▼                       ▼
     │                       role booking              voting live           votes tallied
     │                       open for                  waitlist auto-       waitlist cleared
     │                       members                   cleaned on stop       planner→completed
     │                                                                 projects auto-completed
     │
     └────────────[Delete]────────────────────────────────────────────────────▶[Delete]──▶ (gone)
```

The status transitions are one-way. The button names in brackets are the action buttons in the status group. To re-do a meeting, you create a new one.

---

## Permissions cheat sheet

Most of this tutorial assumes the standard VPE role grants the following permissions. The names below are what shows in the **Settings → Users** page; if a button is greyed out, the corresponding permission is missing.

| Action                                  | Permission needed        |
|-----------------------------------------|--------------------------|
| Create a meeting                        | Meeting Create           |
| Edit agenda (sessions, WOD, projects)   | Meeting Manage           |
| Assign / remove role owners             | Meeting Manage           |
| Publish / Start / Stop the meeting      | Meeting Manage           |
| Delete a finished meeting               | Meeting Create           |
| View all meetings (incl. unpublished)   | Meeting View All         |
| Generate slides / export                | Meeting Manage + the Data/Slides Export module enabled |

If a button is greyed out, you are missing the corresponding permission. Ask a ClubAdmin or check **Settings → Users**.

---

## Where to go next

- **SAA perspective:** `SAA_MemMaker_User_Manual.md` and `SAA_User_Manual_Grid.md` — the SAA's role-by-role checklist for the same cycle.
- **New officer onboarding:** `getting_started.md` — the at-a-glance reference for *every* officer.
- **Pathways deep-dive:** search the `docs/` folder for `pathways` — how projects link to speeches and levels.
- **Template editing:** `template-manager-plan.md` — how to update the agenda template so the next meeting pre-fills correctly.
- **Troubleshooting voting:** `docs/MAILBOX_REALTIME_DESIGN.md` — how live updates flow, in case votes appear to lag.
