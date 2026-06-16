# Customizing Meeting Slides — `slides_layouts.pptx` Guide

This guide is for **club admins** (operations focus, no coding required) who
want to rebrand, recolor, or restyle the slides that VPE Master generates for
each meeting.

**You do not need to know how the app is built.** The only thing you need to
know is that the app looks for PowerPoint **layouts** (the slide templates in
PowerPoint's "Slide Master" view) by **exact name**, and fills specific
**placeholders** (the boxes on a layout) with meeting data. If you keep the
layout names and placeholders in the right spots, the app will fill in the rest
automatically.

If you rename a layout or move its placeholders around, the app will silently
fall back to a default and your changes will not show up. **Read the
"Naming Conventions" section before you touch anything.**

---

## 1. When You Would Use This Guide

Typical reasons to edit the template:

- You want to change colors, fonts, or background images to match your club branding.
- You want to add a logo, watermark, or club photo to the meeting slides.
- You want a "President Awards" or "VPE Special" extra slide in addition to
  the standard slides.
- You want to redesign the section dividers (the slides between segments of
  the meeting).

You do **not** need to edit the template to:

- Add or change meeting content (roles, agenda, speakers) — that is done in
  the web app and shows up automatically.
- Change the order of slides — that follows the agenda you set in the app.
- Add a new club — new clubs get a starter copy of the template automatically.

---

## 2. Where the Template File Lives

Each club has its own copy of the slide template. The file lives on the server
that hosts the VPE Master app, in this folder:

```
app/static/club_resources/<your-club-id>/slides_layouts.pptx
```

`<your-club-id>` is a number. You can find your club id in the URL when you are
logged in as an admin, or by asking the developer who deployed your instance.

There is also a **global seed** file that new clubs are copied from:

```
app/static/club_resources/0/slides_layouts.pptx
```

If a club-specific file is missing, the app falls back to
`instance/layouts.pptx`. You should not normally need to touch either of these
fallbacks — edit the per-club file.

> **Filename note.** The file is called `slides_layouts.pptx` (plural). Do not
> confuse it with `slides_template.pptx` (singular), which is an older file
> used by a legacy code path. **Edit `slides_layouts.pptx`, not the other one.**

### Before you start: back up the file

Make a copy of the existing file and save it somewhere safe (for example
`slides_layouts_backup_2026-06-16.pptx`). If anything goes wrong, you can
restore the original by replacing the file on the server with your backup.

### How you access the file

You need access to the server's file system. Depending on how your VPE Master
is hosted, this is one of:

- **SSH** to the server and edit with a command-line tool, or download with
  `scp` / `sftp` first.
- **FTP / SFTP** client (FileZilla, Cyberduck, etc.) — download, edit locally,
  upload back.
- **Web-based file manager** if your host provides one (cPanel, PythonAnywhere,
  etc.).

There is **no upload UI inside the app**. You must edit the file on the
server's file system directly.

---

## 3. How Slide Generation Works (high level)

When someone downloads meeting slides from the web app, the app:

1. Opens the template file.
2. Looks at the list of "master slide layouts" in the file.
3. For each segment of the meeting, picks the layout that matches what that
   segment needs (a Title Slide, a Role Taker Slide, a section divider, etc.).
4. Fills in the layout's placeholders with the meeting's data (club name,
   speaker name, duration, photo, project info, …).
5. Saves the result as a downloadable `.pptx`.

What this means for you:

- The **layout names** in the template must match what the app looks for. The
  app will use the layout whose name matches exactly (case-sensitive).
- The **placeholders** (the text boxes and picture frames) must be in the
  positions the app expects. If a placeholder is missing, that piece of data
  will not appear on the slide.

That is it. The rest of this guide explains the names and positions you must
preserve.

---

## 4. Layout Naming Conventions (the critical part)

Open the template in PowerPoint and go to **View ▸ Slide Master**. The left
panel shows every layout in the file. Each layout has a name that the app
looks up by exact match. **Do not rename the layouts listed below.**

If you want a layout to be picked up automatically for a specific officer's
segment, name it to start with the officer's role name (see section 4.2).

### 4.1 Required layouts

The template **must** contain layouts with these exact names. If any are
missing, the app will either use a generic default or skip the slide silently.

| Layout name                | Purpose                                                                   |
|----------------------------|---------------------------------------------------------------------------|
| `Title Slide`              | First slide of every deck — club name + meeting number / date            |
| `section_action`           | "Action / Agenda" slide shown right after the Title Slide                 |
| `section_agenda`           | Alternative name for the same Action / Agenda slide (either name works)  |
| `section_opening`          | Divider shown before the Opening segment                                  |
| `section_evaluations`      | Divider shown before the Evaluation segment                               |
| `section_preparedspeeches` | Divider shown before Prepared Speeches                                    |
| `section_voting`           | Divider shown before Awards & Closing                                     |
| `section_networking`       | Layout used for Networking sessions                                       |
| `section_tabletopics`      | Divider shown right after a Table Topics session                          |
| `Keynote Speaker Slide`    | Layout for the Keynote Speech session                                     |
| `Prepared Speaker Slide`   | Layout for each Prepared Speech session                                   |
| `Role Taker Slide`         | Default layout for every other role (Timer, Ah-Counter, Grammarian, etc.) |

> **Tip.** Section dividers (`section_*`) are inserted into the deck as-is.
> The app never edits their text or images. This means you have full creative
> control over the visual design of dividers — make them as branded or
> as minimal as you like.

### 4.2 Officer extras: the "starts with the role name" rule

For sessions held by club officers (President, VPE, VPM, VPPR, Secretary,
Treasurer, SAA, …), the app will automatically add **extra slides** for any
layout whose **name starts with the officer's role name** (case-insensitive).

**Examples that the app will pick up automatically:**

- `President_1` — extra slide for the President
- `President_2` — another extra slide for the President
- `VPE_1`, `VPE_2` — two extra slides for the VPE
- `President_Address` — extra slide for the President's address
- `VPM_Award` — extra slide for an award ceremony

The app fills these extra slides with the **same data** as the regular role
taker slide (title, name, duration, photo, project info), so make sure the
extra layouts have the same placeholders as the standard layouts (see
section 5).

If you do **not** want an extra slide for a given officer, simply do not
create a layout whose name starts with that officer's role name. The match is
opt-in.

### 4.3 What if I need to rename a layout?

In almost all cases, **do not rename the layouts listed in section 4.1**. If
you rename one:

1. The app will not find it.
2. The app will fall back to a default (or skip the slide) silently.
3. You will not see an error — your changes just will not appear in the
   generated slides.

If you have a strong reason to rename a layout (for example, your club uses
non-English agenda names and you want a localized label), ask a developer to
also update the app's lookup strings. The dev can find them in
`app/services/meeting_slide_service.py` by searching for `layouts.get(`.

---

## 5. Placeholder Conventions

Every layout that the app fills with data has a set of **placeholders** —
the text boxes, picture frames, etc. that the app writes into. The app fills
placeholders based on their **position in the layout** (first, second, third,
…). Placeholder positions are stable per layout, but they are determined by
the order placeholders appear in the Slide Master view. **If you reorder, add,
or delete placeholders, the app will write the wrong data into the wrong
spot.**

### 5.1 The Title Slide layout

| Position | What the app fills in                  |
|----------|----------------------------------------|
| 1st      | Club name (e.g. `Acme Toastmasters Club`) |
| 2nd      | `Meeting <n> / <DD-MMM-YYYY>`          |

### 5.2 The standard role / speaker layouts

This applies to: `Keynote Speaker Slide`, `Prepared Speaker Slide`,
`Role Taker Slide`, and any `<Officer>_<suffix>` layout.

| Position | What the app fills in                                                       |
|----------|-----------------------------------------------------------------------------|
| 1st      | Session title (e.g. `Prepared Speech 1`). For Evaluators: `Individual Evaluator for` followed by the speech title. |
| 2nd      | Name and credentials: `Name, Credentials`. For two owners: `Name1, creds1 & Name2, creds2`. |
| 3rd      | Duration: `2-3'` (range) or `3'` (single value).                            |
| 4th      | **Member photo** — the app inserts the speaker's avatar image here.          |
| 5th      | Project info: `<project_code> - <project_name>` for Prepared Speeches; empty otherwise. |

### 5.3 What to do in PowerPoint

For each of the layouts above, you need **at least five placeholders**, in
this order:

1. **Title** placeholder (text)
2. **Subtitle / Name** placeholder (text)
3. **Duration** placeholder (text)
4. **Picture** placeholder (use Insert ▸ Placeholder ▸ Picture — not just a
   rectangle)
5. **Project info** placeholder (text)

You can move them anywhere on the slide, resize them, change their fonts, and
restyle them however you want. What you **must not** do is:

- **Delete the picture placeholder (position 4).** If it is missing, member
  photos will silently disappear from the slides. If you do not want photos,
  keep the placeholder but make it invisible (move off-slide, set fill to
  none, or set its size to zero).
- **Reorder the placeholders.** PowerPoint assigns positions in the order
  they appear in the layout. Reordering will swap the data.
- **Use a regular rectangle for the picture.** The app calls
  `insert_picture()` on a real picture placeholder, which only works on actual
  picture placeholders. A rectangle will leave the photo slot blank.

### 5.4 Section dividers need no placeholders

Section layouts (`section_*`) are inserted as-is. You do not need to set up
any placeholders on them. Add any background, logo, or visual you want — the
app will not touch it.

---

## 6. Editing the Template — Step-by-Step

### 6.1 Open the file

Download the file from the server to your local computer, then open it in
PowerPoint, Keynote, or LibreOffice Impress. Use **File ▸ Open** — do **not**
drag-and-drop it into another presentation, or you will lose the Slide Master
structure.

### 6.2 Open Slide Master view

- **PowerPoint:** View tab ▸ Slide Master. The left panel lists every master
  layout. The big editing area shows the selected layout with all its
  placeholders.
- **Keynote:** Edit Master Slides button in the toolbar.
- **LibreOffice:** View ▸ Master Slide.

### 6.3 Verify the layout names match section 4

Click each layout in the left panel. The layout name appears at the top of
the editing area (in PowerPoint, also in the Slide Master ribbon under
"Layout Name"). Compare each name to the table in section 4.1.

If any name is missing or misspelled, fix it now (see section 6.5 for safe
renames — but in general, keep these names exactly as listed).

### 6.4 Edit visually

You can safely change:

- Colors, gradients, theme colors
- Fonts (theme fonts and individual run formatting)
- Background images and watermarks
- Logo placement and size
- The position, size, font, alignment, and rotation of any placeholder
- The fill, border, and shadow of any shape
- Adding decorative shapes, lines, or images anywhere on a layout

You should **avoid**:

- Renaming the layouts in section 4.1 (or coordinate with a developer if you
  must).
- Deleting the picture placeholder at position 4 on role/speaker layouts.
- Reordering the standard placeholders (positions 1–5).
- Adding new layouts whose names do not follow the `<Officer>_<suffix>` rule
  unless you intend them to be picked up automatically.

### 6.5 Save and upload

Save the file locally first, then upload it back to the server, overwriting
the original at:

```
app/static/club_resources/<your-club-id>/slides_layouts.pptx
```

The path and filename must not change. **Do not** save it as a `.pptx` from
Keynote unless you have tested the round-trip — Keynote sometimes drops
features that the app relies on. PowerPoint or LibreOffice are safer choices.

There is no need to restart the app or trigger a rebuild. The next time
someone downloads a meeting deck, the new template will be used.

---

## 7. Adding a New Layout

To add an extra officer-specific slide (for example, a "President Awards"
slide):

1. In Slide Master view, click **Insert Layout** (PowerPoint ribbon).
2. Rename the new layout to something that starts with the officer's role
   name, e.g. `President_Awards`.
3. Add the five standard placeholders described in section 5.2 (Title, Name,
   Duration, Picture, Project Info).
4. Style the layout however you want.
5. Save the file locally, then upload it back to the server.
6. Download a test meeting deck that includes a session for the President.
   The new `President_Awards` slide should appear right after the standard
   President role-taker slide, filled with the same data.

If the new layout name does **not** start with an officer role, the app will
not pick it up automatically. The app does not currently provide a way to map
arbitrary layouts to specific sessions — name-based matching is the only
mechanism.

---

## 8. Verifying Your Changes

There is no separate "build" step. The next meeting slide download will use
the updated template. To verify:

1. Log in to the web app as a user with download permission.
2. Open any meeting.
3. Trigger the slide download (the exact button depends on your version of
   the app — typically on the meeting agenda page).
4. Open the downloaded `.pptx` and check:
   - The Title Slide shows your club name and the meeting number / date.
   - Every section divider you styled appears in the right place.
   - Officer-specific slides (e.g. `President_1`, `VPE_2`) appear where
     expected.
   - Member photos appear on role-taker and speaker slides (if your members
     have photos uploaded).

### Common issues and what they mean

| What you see                                                    | Most likely cause                                                       |
|-----------------------------------------------------------------|-------------------------------------------------------------------------|
| A divider slide is missing entirely                             | The corresponding `section_*` layout was renamed or deleted.            |
| All section dividers are missing                                | The template file failed to load — ask a developer to check the server logs. |
| Officer extra slides do not appear                              | The layout name does not start with the role name (case-insensitive).   |
| Member photos are blank                                         | The picture placeholder (position 4) was deleted, or is not a real picture placeholder. |
| Title text appears in the wrong shape                           | Placeholders were reordered — restore the order Title → Name → Duration → Photo → Project Info. |
| Duration text appears in the wrong shape                        | A placeholder is missing from the layout.                               |
| A slide is generated from `Role Taker Slide` instead of your custom layout | Layout name typo — names are case-sensitive.                  |

### Rolling back

If anything looks wrong, restore the backup copy you made in section 2 by
uploading it back to the same path. The next download will use the restored
template.

---

## 9. Quick Reference Card

**Layouts that must exist (exact, case-sensitive names):**

```
Title Slide
section_action     (or section_agenda — either works)
section_opening
section_evaluations
section_preparedspeeches
section_voting
section_networking
section_tabletopics
Keynote Speaker Slide
Prepared Speaker Slide
Role Taker Slide
```

**Optional officer extras (any name starting with the role name):**

```
President_1, President_2, VPE_1, VPE_2, President_Awards, ...
```

**Placeholders in order on role / speaker layouts:**

```
1. Title            — filled with session title
2. Name, Credentials
3. Duration         — e.g. "2-3'"
4. Photo            — must be a real picture placeholder
5. Project info     — "code - name" for Prepared Speeches
```

**Section dividers** (`section_*`) need no placeholders — design only.

---

## 10. When to Ask a Developer

You are working outside the app's normal UI, so a few things still require a
developer:

- Renaming any layout in section 4.1 (the app's lookup strings need to be
  updated too).
- Adding layouts that are not officer-related (the app does not currently
  support name-based matching for non-officer roles).
- Diagnosing why the template file is failing to load (check server logs).
- Any change that requires editing files other than
  `slides_layouts.pptx` (for example, the legacy `slides_template.pptx`).

For everything else — colors, fonts, logos, placeholder restyling, new
officer extras — you can make the change yourself by editing the template in
PowerPoint and uploading it back.
