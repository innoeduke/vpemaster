Based on the provided source code, here is a comprehensive feature list for the **vpemaster** application, structured by module, capabilities, and specific features.

### **Module 1: Meeting & Agenda Management**
**Capability:** comprehensive planning and execution of club meetings.

* **Feature: Meeting Creation & Scheduling**
    * **Create from Template:** Initialize meetings using CSV templates (e.g., Default, Debate, Speech Contest, Panel Discussion).
    * **Meeting Details:** Manage title, subtitle, "Word of the Day" (WOD), meeting type, and date/time.
    * **Media Linkage:** Associate a meeting video URL (e.g., Zoom recording) with the meeting record.

* **Feature: Agenda Management**
    * **Session Editing:** Add, update, or delete individual agenda items (Session Logs).
    * **Dynamic Timing:** Automatically recalculate session start times based on duration and previous items. Handles breaks for "Multiple shots" GE styles.
    * **Section Management:** Support for "Section Headers" and hidden items to organize the flow without affecting the timeline.
    * **Meeting Status Lifecycle:** Toggle status between 'Not Started', 'Running', 'Finished', and 'Cancelled'.

* **Feature: Reporting & Export**
    * **Excel Export:** Generate a 3-sheet Excel file containing the Formatted Agenda, PowerBI Data Dump, and Roster.
    * **PowerBI Integration:** Specific data formatting (Yoodli links, detailed role tracking) designed for PowerBI dashboards.

### **Module 2: Role Booking & Participation**
**Capability:** User self-service and administrative assignment of meeting roles.

* **Feature: Role Assignment**
    * **Self-Booking:** Users can sign up for open roles for upcoming meetings.
    * **Admin Override:** Officers can assign or unassign any user to any role.
    * **Waitlist System:** Users can join a waitlist for taken roles; Admins can promote waitlisted users to the active role.
    * **Approval Workflow:** Certain roles can be flagged as "Needs Approval," requiring admin intervention before confirmation.

* **Feature: Booking Logic & Restrictions**
    * **Backup Speaker Rule:** Prevents users from double-booking if they are already a backup speaker (unless booking the same role).
    * **3-Week Policy:** Warns or restricts users from booking a speech if they have spoken in the last 3 meetings.

* **Feature: Voting System**
    * **Award Categories:** Support for voting on Best Speaker, Best Evaluator, Best Role Taker, and Best Table Topic.
    * **Vote Tracking:** Records votes linked to specific meetings and contacts.

### **Module 3: Educational Pathways (Speech Tracking)**
**Capability:** Management of Toastmasters educational progress and speech history.

* **Feature: Speech Logging**
    * **History View:** Users can view their own speech history; Admins can view all. Filters available for Meeting, Pathway, Level, and Status.
    * **Speech Details:** Edit speech title, associate with a specific Project ID, and link media (video).

* **Feature: Progress Automation**
    * **Status Management:** Mark speeches as 'Delivered' or 'Completed'.
    * **Auto-Advance:** When a speech is marked completed, the system automatically calculates the user's next project/level based on Pathway logic.

* **Feature: Project Library**
    * **Curriculum Browser:** View details for all Toastmasters projects, including Introduction, Overview, Purpose, Requirements, and Resources.
    * **Content Editing:** Admins can update project descriptions using Markdown support.

### **Module 4: Member & Contact Management**
**Capability:** A directory system for managing club members and guests.

* **Feature: Contact Directory**
    * **Search & Filter:** Search contacts by name; filter by type (Member vs. Guest).
    * **CRUD Operations:** Create, read, update, and delete contact records.

* **Feature: Profile Details**
    * **Member Attributes:** Track email, phone, bio, DTM status, and completed education paths.
    * **User Association:** Link generic Contact records to specific User login accounts.

### **Module 5: Administration & Settings**
**Capability:** System configuration and definitions.

* **Feature: Session & Role Configuration**
    * **Session Types:** Define and update session types (e.g., "Keynote," "Table Topics") with default durations and owners.
    * **Role Definitions:** Create and edit roles, assign icons, and determine if they are "Distinct" (one per meeting) or require approval.
    * **Import Roles:** Bulk import role definitions via CSV.

* **Feature: Club Settings**
    * **General Config:** Manage global settings like Club Name and default Meeting Start Time.

### **Module 6: Roster Management**
**Capability:** Managing attendance order and ticketing for specific meetings.

* **Feature: Ticket System**
    * **Order Tracking:** Assign order numbers and "Ticket" classes to attendees for specific meeting numbers.
    * **Assignment:** Link specific Contacts to roster slots.
    * **Cancellation:** Support for cancelling roster entries.

### **Module 7: Authentication & Security**
**Capability:** Secure access control.

* **Feature: Access Control**
    * **Authentication:** Secure login/logout using hashed passwords.
    * **Role-Based Access:** Granular permissions (e.g., `BOOKING_ASSIGN_ALL`, `SETTINGS_VIEW_ALL`, `CONTACT_BOOK_EDIT`) restricting access to specific routes.
    * **Profile Management:** Users can update their email, phone, bio, and reset passwords.