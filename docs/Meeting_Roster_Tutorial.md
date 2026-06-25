# Memory Maker — Tutorial: Managing the Meeting Roster

> **Audience:** Treasurer (primary), with the Sergeant at Arms (SAA) and Vice President Education (VPE) as supporting readers. No coding background assumed.
> **Goal:** Walk through every screen and action involved in managing a meeting's roster — from the week before the meeting through the Treasurer's reconciliation.
> **Last updated:** 2026-06-24

The **roster** is the official attendance list for a meeting. Each row represents one person who plans to attend: their name, their ticket type (member early-bird, member walk-in, guest early-bird, guest walk-in, or officer), their amount paid, and whether they've checked in. The roster is the source of truth for *who was in the room* and *who paid what*.

As Treasurer, you are the primary owner of the roster's financial side — ticket types, amounts collected, exports for the club's books. The SAA handles the operational side at the door (registering walk-ins, marking check-ins, monitoring attendance in real time). The VPE helps when the meeting's structure changes (cancelling a meeting, swapping in a substitute) or when a member's role assignment needs to be reflected in the roster. Members only see the roster indirectly, through the booking page where they self-register for roles — that page is covered separately in the booking tutorial.

The full cycle has four phases:

1. **Phase 1 — Pre-Meeting Preparation** (T-7 days to T-1 day): confirm the meeting exists, review ticket types, understand the roster page.
2. **Phase 2 — Reception & Check-In** (T-0, 6:30 PM – 7:15 PM): register members and guests, assign tickets, monitor attendance.
3. **Phase 3 — Live Meeting** (T-0, 7:00 PM – 9:00 PM): handle late arrivals, last-minute changes, and check-in corrections.
4. **Phase 4 — Wrap-Up** (T+0, 9:00 PM – end): export the final roster, seal the meeting, archive.

---

## Phase 1 — Pre-Meeting Preparation

Most of the roster's value comes from data that has already been entered before the meeting. By the time the doors open, you should know roughly how many people are coming, what the expected revenue is, and which members have already self-registered for roles.

### 1.1 Open the Roster page

In the top navigation bar, click **Roster**. The page is divided into four regions:

- **Meeting selector** (top): pick which meeting you're working on. The dropdown only lists meetings for your current club.
- **KPI panel** (just under the selector): three numbers — *attendees*, *total amount*, and *checked-in count*. These update live as people register and arrive.
- **Roster table**: one row per person, with columns for name, ticket type, amount, check-in status, and any assigned roles.
- **Add Entry form** (only visible if you have edit permission): a quick-add panel for walk-ins and last-minute registrations.

> **Tip:** If you don't see the Add Entry form, your account is missing the **Roster Edit** permission. Officers (VPE, VPM, SAA, President, Secretary, Treasurer) typically have it; ordinary members don't. Ask a ClubAdmin if you need it.

### 1.2 Verify the meeting exists and is published

The roster page only shows meetings that have been created on the Agenda page. If the dropdown is empty for the upcoming meeting:

1. Switch to the **Agenda** page.
2. Ask the VPE to create the meeting from a template (see `VPE_MemMaker_Tutorial_NonTechnical.md`, Phase 1.2).
3. Once the meeting exists, return to the Roster page and pick it from the dropdown.

A meeting can be **Unpublished**, **Not Started**, **Running**, or **Finished**. All four states allow roster entries to be added. The state only restricts other actions — for example, the Self Check-In QR only appears when the meeting is *Not Started* or *Running*.

### 1.3 Review the ticket types

Each roster entry must have a ticket type. Early-bird and Walk-in are each priced differently depending on whether the attendee is a **member** or a **guest**, so the catalogue effectively runs to five tickets. Configure them in **Settings → Tickets**:

| Ticket | Price | When to use |
|--------|-------|-------------|
| **Member · Early-bird** | ¥20 | Members who paid before **15:00 on the meeting day** |
| **Member · Walk-in** | ¥25 | Members who pay at the door (after the 15:00 cutoff) |
| **Guest · Early-bird** | ¥40 | Guests who paid before 15:00 on the meeting day |
| **Guest · Walk-in** | ¥50 | Guests who pay at the door (after the 15:00 cutoff) |
| **Officer** | ¥0 | Current ExComM members |

> **The 15:00 cutoff is firm.** Anyone whose payment hasn't landed in the Treasurer's record by 15:00 on meeting day is automatically a Walk-in. Don't argue the time zone — the cutoff is local club time, not UTC.

The price column on a roster row is auto-computed from the ticket's price × quantity, so you don't need to enter amounts by hand. If a row shows the wrong amount, the ticket type is wrong — change it and the amount recalculates.

### 1.4 Understand who appears on the roster

Three groups of people end up on the roster:

- **Members who self-registered via the booking page** — they have a role assignment (Speaker, Evaluator, Timer, etc.) and a ticket assigned automatically. You usually don't touch these rows.
- **Members who walked up to the door and told you they're here** — you add them manually through the Add Entry form.
- **Guests** — always added manually, because guests don't have accounts.

When a member cancels their role booking, Memory Maker automatically removes them from the roster. When a member books a new role, they're added (or their existing unallocated row is updated). As Treasurer, you rarely need to manually create rows for members — but you should still scan the roster before the meeting to confirm each member's ticket type is correct (some members pay in advance via WeChat and never interact with the booking page; others pay at the door and need a Walk-in ticket assigned).

### 1.5 Pre-meeting checklist (T-1 day)

The day before the meeting, run through this:

- [ ] The meeting exists in the dropdown.
- [ ] KPI panel shows a sensible attendee count (not zero — if it is, members haven't booked yet; send a reminder).
- [ ] Total amount roughly matches what the Treasurer expects.
- [ ] All current officers have an *Officer* ticket (add manually if missing — the system can't tell who is currently an officer).
- [ ] The Self Check-In QR button is visible (if your club uses Self Check-In).

If any of these are off, fix them now — they're much harder to correct during the rush of reception.

---

## Phase 2 — Reception & Check-In (6:30 PM – 7:15 PM)

The room is filling up. Members and guests are walking in. Your job is to register everyone who arrives, so the Treasurer's records are accurate.

### 2.1 Open the roster on a second device (recommended)

If you have a tablet or a second laptop, open `/roster` on it and keep it next to the entrance. Members can scan a Self Check-In QR (if enabled) to register themselves, and you can watch the check-in count climb in real time.

### 2.2 Set up Self Check-In (optional)

If your club uses the Self Check-In module:

1. On the Roster page, look for the **Self Check-In** button (top-right of the page). It's only visible when the meeting is *Not Started* or *Running*.
2. Click it to reveal the QR code or the short check-in URL.
3. Project the QR on the TV, print it as a tent card on the entrance table, or paste the URL into the club's WeChat group.

When a member scans the QR, the system registers their check-in. Guests can't use Self Check-In because they need to be on the roster first.

> **Tip:** Even with Self Check-In enabled, you'll still walk-ins. The QR is for *members who already have a roster entry* — guests and unbooked walk-ins still need you to add them manually.

### 2.3 Register a guest or walk-in

When someone walks up who isn't on the roster yet:

1. In the Add Entry form, type the person's name in the **Contact** field. Memory Maker searches as you type — pick the existing contact if it appears.
2. If the search returns no result, click **+ New Contact** and fill in: name, mobile, email (if available), and contact type (Guest or Member).
3. Pick the **Ticket Type** (Walk-in, Early-bird, or Guest — depending on what they're paying).
4. Set the **Quantity** (usually 1; some clubs allow members to bring a +1).
5. Click **Add**. The row appears in the table with the order number auto-assigned.

> **Tip:** If the same person comes to multiple meetings, Memory Maker will suggest their contact from history. Over time, the dropdown fills out and you stop typing.

### 2.4 Edit an existing entry

Sometimes a row needs to be fixed:

- **Wrong ticket type** — click the ticket cell and pick the correct one. The amount recalculates.
- **Wrong contact** — click the name cell and re-pick from the dropdown.
- **Wrong quantity** — click the quantity cell and edit. The amount recalculates.
- **Mark as checked in** — click the check-in cell (a checkbox or toggle, depending on your club's settings). The current time is recorded as the check-in time.

### 2.5 Monitor the KPI panel

Throughout reception, glance at the KPI panel every few minutes:

- **Attendees** should be climbing. If it's flat for too long, members may not have seen the booking reminder.
- **Total amount** should match your expected cash inflow. **This is your primary number as Treasurer** — discrepancies are almost always a wrong ticket type on one row (a member marked as *Walk-in* who actually paid the *Early-bird* rate, or vice versa). Fix the ticket type and the amount recalculates.
- **Checked-in count** lags behind attendees because not everyone uses Self Check-In. The gap is normal.

> **Tip:** Cross-check the running total against the cash in your envelope every 30 minutes. If the envelope has ¥200 more than the panel shows, someone paid cash and wasn't added to the roster — find them on the floor and add their row.

### 2.6 Late registrations

If someone arrives after 7:00 PM (after the meeting has started), the flow is the same — add them as a walk-in, assign a ticket. The meeting status doesn't block roster edits.

---

## Phase 3 — Live Meeting (7:00 PM – 9:00 PM)

During the meeting, the roster is mostly read-only. Your job is to keep it accurate as people come and go.

### 3.1 Handle late arrivals

A member who texts "I'm running 15 min late" should be added to the roster **before** they arrive, with a note (e.g. "Late — coming at 7:30") in the **Notes** field. This ensures:

- They're counted as an expected attendee even if they walk in after you close check-in.
- The Treasurer can match their payment when they finally arrive.

If they never arrive, leave them on the roster. Cancelling an entry mid-meeting is more disruptive than letting it sit (see 3.4).

### 3.2 Add a substitute for an absent role-holder

If the Timer calls in sick at 7:05 PM:

1. Find the absent member's roster row.
2. Look at the **Roles** column — it shows the role(s) they had booked.
3. On the **Agenda** page, reassign the role to the substitute (see `VPE_MemMaker_Tutorial_NonTechnical.md`, section 3.3). The booking system handles this; you don't edit the roster directly.
4. The substitute's roster row will gain the role automatically the next time the booking page refreshes.

> **Heads up:** Don't try to edit the Roles column on the roster row directly. Roles are managed through the booking flow, not the roster. Editing them here will be overwritten the next time someone touches the booking page.

### 3.3 Mark someone as checked in

If Self Check-In is on but someone couldn't scan the QR (camera broken, phone dead, etc.):

1. Find their row in the table.
2. Click the check-in cell. The status flips to *Checked in* and the time is recorded.

You can also undo a check-in (if someone accidentally double-scans and the wrong time got recorded) by clicking the cell again — it toggles back to *Not checked in*.

### 3.4 Cancel or restore an entry

Two ways to remove someone from the roster mid-meeting:

- **Soft cancel (the default):** Click the **Cancel** button on the row. The entry stays in the database but is marked *Cancelled*. Their ticket is released, but the row is still visible in the table (greyed out). Use this for most cases — it preserves the audit trail.
- **Hard delete (advanced):** Click **Delete** with the `?hard_delete=true` option. The row is removed, and any role booking they had is released back to the pool. Use this only if:
  - The entry was a duplicate.
  - The entry was created by mistake (wrong meeting, wrong contact).
  - You need the role slot back urgently because the meeting is starting.

> **Heads up:** Hard delete is permanent for that meeting. If you hard-delete a member who actually paid, you've erased the payment record from this meeting. Always prefer soft cancel unless you know for sure the entry is bogus.

If you soft-cancelled by mistake:

1. Find the row (it's still there, greyed out).
2. Click **Restore**. Memory Maker re-issues a sensible ticket (the same one if it's still appropriate, or *Walk-in* if the original ticket was a one-off).

### 3.5 View participation trends

If the meeting is dragging and you're curious about long-term patterns:

- **Participation trend** (button at the top of the Roster page): a chart of attendees per meeting over the last N meetings. Useful for showing the VPE that attendance is dropping or rising.
- **Amount trend**: a chart of revenue per meeting. Useful for the Treasurer.

Both pages are read-only — they don't change any data.

---

## Phase 4 — Wrap-Up (9:00 PM – end)

The General Evaluator is wrapping up. Time to seal the roster.

### 4.1 Stop adding entries

At the end of the meeting, stop accepting new roster entries. Late walk-ins after this point should be told to register for next week instead. The reason: the meeting is closing out — adding entries after the meeting is finished pollutes the export and the audit trail.

If a member insists, add them — but note in the **Notes** field that they arrived late.

### 4.2 Export the final roster

Click the **Export** button (top-right of the Roster page) and pick your format:

- **PDF** — the default. Printable, signed, and filed. **This is the document that goes into the Treasurer's binder as the meeting's financial record.** Includes every non-cancelled entry with ticket type, amount, and check-in status.
- **CSV** — for importing into a spreadsheet when you do the month-end reconciliation against the bank statement.
- **Image (.png)** — for the post-meeting recap in the club's WeChat group.

As Treasurer, the PDF export is your primary deliverable for the meeting. Save it under a consistent filename (e.g. `YYYY-MM-DD-meeting-NN-roster.pdf`) so future Treasurers can find it.

### 4.3 Soft-cancel no-shows (the day after, before reconciliation)

The morning after the meeting, walk through the roster and soft-cancel anyone who:

- Was registered but didn't show up.
- Marked themselves as coming but cancelled at the door.

Don't hard-delete — soft-cancel preserves the record that they were expected. This matters for two reasons:

- It keeps the participation-trend chart honest (a no-show is still an expected attendee; a hard delete erases them).
- **It gives you, as Treasurer, the audit trail for "expected vs. actual" attendance** — when a member disputes a charge ("I paid for last week, I wasn't even there"), you can show that they were registered, marked as a no-show, and the ticket was released.

> **Tip:** Do this *before* you reconcile against the bank statement, not after. Reconciling against a roster that still shows ghost attendees makes the numbers confusing.

### 4.4 The meeting moves to *Finished*

Once the VPE clicks **Stop** on the Agenda page, the meeting status changes to **Finished**. From this point:

- Voting closes, votes are tallied, and the SAA reads out the results.
- The roster is locked for normal editing — you can still view it, but the Add Entry form hides itself.
- The Self Check-In QR disappears.

If you genuinely need to edit a finished meeting's roster (e.g. a Treasurer found a payment error a week later), ask a ClubAdmin — they have an override that can re-open the editor. Don't try to circumvent this on your own; the audit trail is more important than the speed of the fix.

---

## Quick Reference: Roster Status Flow

```
   Meeting created (VPE)
            │
            ▼
   Pre-meeting  ──SAA reviews roster, sets up Self Check-In──▶ Reception
                                                                 │
                                                                 ▼
                                                          Live meeting
                                                          ──walk-ins, swaps,
                                                            check-in toggles──
                                                                 │
                                                                 ▼
                                                          Meeting stops
                                                          ──KPI frozen, exports,
                                                            soft-cancel no-shows──
                                                                 │
                                                                 ▼
                                                          Meeting = Finished
                                                          ──roster locked,
                                                            archive only
```

The roster is editable at every stage from *Pre-meeting* through *Live meeting*. Once the meeting is *Finished*, edits require ClubAdmin intervention.

---

## Common tasks cheat sheet

| Task | Where on the Roster page | Permission needed |
|------|--------------------------|-------------------|
| View the roster | Open `/roster` | Roster View |
| Add a guest or walk-in | Add Entry form | Roster Edit |
| Edit ticket type / amount | Click the cell | Roster Edit |
| Mark as checked in | Click the check-in cell | Roster Edit |
| Soft-cancel an entry | Cancel button on the row | Roster Edit |
| Restore a soft-cancelled entry | Restore button on the row | Roster Edit |
| Hard-delete an entry (releases role slot) | Delete with `?hard_delete=true` | Roster Edit + Meeting Manage |
| Show the Self Check-In QR | Self Check-In button | Roster Edit + Self Check-In module |
| View participation trend | Trend button | Roster View |
| View amount trend | Trend button | Roster View |
| Export final roster | Export button | Roster View |

If a button is greyed out or missing, you are missing the corresponding permission. Ask a ClubAdmin or check **Settings → Users** for your role's grants.

---

## Permissions cheat sheet

| Action | Permission needed | Typical roles |
|--------|------------------|---------------|
| View the roster for a meeting | Roster View | Member and above |
| Add / edit / cancel entries | Roster Edit | Officer and above |
| Hard-delete an entry | Roster Edit + Meeting Manage | VPE / ClubAdmin |
| Override a finished meeting's roster | ClubAdmin override | ClubAdmin only |

**Sharing-master override:** If you are the meeting's *sharing master* (the person designated in the Agenda page as the official host of that meeting), Memory Maker automatically grants you **Roster Edit** and **Roster View** for that meeting, even if your normal role doesn't include them. This is so a guest host can manage the roster on the night without needing a permanent role grant.

---

## Troubleshooting

**The Add Entry form is hidden.** You don't have Roster Edit. Either it's intentional (your account is a plain Member) or your role grant is missing. Check **Settings → Users**.

**I soft-cancelled the wrong person.** Click **Restore** on the row. The ticket type is preserved. If the ticket was one-off (e.g. a special event ticket), the system may substitute a generic Walk-in — fix the ticket type manually after restoring.

**The Self Check-In QR is greyed out.** Either the meeting isn't in *Not Started* or *Running* state, or the Self Check-In module isn't enabled for your club. Ask a ClubAdmin.

**Two members have the same name.** Memory Maker distinguishes them by their internal contact ID, not by name. The roster table shows enough of the mobile / email to tell them apart. If the rows are still confusing, ask the members to update their profile with a clear name.

**I hard-deleted an entry by mistake.** This is the one operation that can't be undone from the UI. The good news: the original ticket payment is recorded in the Tickets table — you can still see it in the Tickets page, and the row's absence from the roster is itself a flag during reconciliation. But the roster row itself is gone. Re-create it as a new entry and manually link the payment in your spreadsheet.

---

## Where to go next

- **Tickets page:** the Tickets section of the app is your companion to the roster — it tracks each ticket's payment status, refund history, and ties a payment to a specific roster entry. When reconciling against the bank statement, cross-reference Tickets (which is the payment ledger) with the roster (which is the attendance ledger).
- **Booking & role assignments:** see the booking tutorial (link in the docs index) — covers `/booking`, self-registration, waitlists, officer approval. Useful for understanding why members appear on the roster without you adding them.
- **VPE perspective:** `VPE_MemMaker_Tutorial_NonTechnical.md` — covers the meeting lifecycle from the VPE side, including how role assignments interact with the roster.
- **SAA perspective:** `SAA_MemMaker_User_Manual.md` and `SAA_User_Manual_Grid.md` — the SAA's door-side checklist for the same meeting.
- **Permissions:** `access_matrix.md` — the default role × permission matrix, including Roster View / Roster Edit.
- **Self Check-In module setup:** search the docs for "Self Check-In" — module-level setup (QR display device, network reachability, fallback for offline mode).