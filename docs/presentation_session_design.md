# Presentation Session Type - Design Document

This document outlines the architecture, data models, and logic for supporting the global **Presentation** session type in `vpemaster`.

---

## 1. Core Architecture

The Presentation session type represents a special category of Prepared Speech. It is designed to track progress and award credit for speaking roles that utilize the Toastmasters educational presentation series (e.g., *Successful Club Series*, *Better Speaker Series*, *Leadership Excellence Series*).

### UI Integration
- Presentations share the standard **Prepared Speech** modal layout.
- Both Pathway select and Level select elements remain visible and functional.

### Pathway & Level Bounds
- **Target Levels**: Constrained exclusively to **Level 3**, **Level 4**, and **Level 5**.
- **Pathway Binding**: Presentation session logs and their corresponding `OwnerMeetingRoles` (OMR) records are bound to a target pathway (e.g., "Presentation Mastery"). 
- **Project Selection**: Unlike prepared speeches, presentation projects are the same across all pathways. However, a completed presentation project is **only bound to the pathway under which it was completed**.

---

## 2. Backend Design

### 2.1 Recommendation Engine (`/speech_log/presentation_projects`)
We expose a GET endpoint to fetch recommended projects for the owner's active level:
- **Parameters**:
  - `contact_id` (int, required): The ID of the speaker.
  - `level` (int, optional): The level to query projects for. Defaults to the speaker's derived target level (minimum of level 3).
  - `current_project_id` (int, optional): The ID of the currently selected project (so it is not excluded if it was already marked completed).
  - `pathway` (str, optional): The target pathway name. Defaults to the speaker's `Current_Path`.

- **Filtering Completed Projects**:
  To support pathway-specific completion scoping, completed presentation projects are queried by joining `OwnerMeetingRoles` and filtering where `target_pathway` matches the queried pathway (or is null/empty if querying for "Non Pathway"). Completed projects from other pathways are not excluded.

### 2.2 Persistence & Database Fields
- Saved via the standard `update_speech_log` POST route.
- Saves `OwnerMeetingRoles.target_pathway` and `OwnerMeetingRoles.target_level` normally.
- Excluded from affecting `Next_Project` calculations in the contact's profile (as presentations are elective/series speech logs rather than linear pathway projects).

---

## 3. Frontend Workflow

In `speech_modal.js`, the `SpeechModalSetupManager.setupSpeech` manages the setup sequence:

1. **Restricting Levels**: When `sessionType === "Presentation"`, the Level select options are populated with only Levels 3, 4, and 5.
2. **Mounting Owner Picker**: The owner picker dynamically sets the speaker, pathway, and level. If the derived level is less than 3, the frontend defaults it to Level 3.
3. **Dynamic Re-fetching**:
   We bind change listeners to Level, Pathway, and Owner selections.
   - When the owner is changed, we programmatically update the pathway and level, then trigger a single fetch for presentation projects.
   - When the level or pathway changes manually, we trigger a fetch to load presentation projects for the new state, automatically hiding completed projects for the newly selected pathway.
4. **Saving**: The payload is built with the selected pathway and level, sending them directly to the backend update endpoint.

---

## 4. Verification

Verification is covered by unit tests in `tests/test_presentation_session.py`:
- `test_presentation_projects_endpoint`: Asserts that presentation projects are correctly filtered by level, completed projects are filtered out specifically for the target pathway, and they default to level 3 when the contact has a lower target level.
- `test_presentation_omr_save`: Verifies that the update endpoint successfully saves both pathway and level to `OwnerMeetingRoles`, and behaves correctly when saving under "Non Pathway".
