# VPEMaster API Reference

Last updated: 2026-04-24

---

## Users

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/user/form` | Create user (form) |
| POST | `/user/form` | Create user (submit) |
| GET | `/user/form/<id>` | Edit user (form) |
| POST | `/user/form/<id>` | Edit user (submit) |
| GET | `/users` | List all users |
| POST | `/user/bulk_import` | Bulk import users from CSV |
| POST | `/user/check_duplicates` | Check for duplicate emails |
| POST | `/user/delete/<id>` | Delete user |
| POST | `/user/request_join` | Member requests to join club |
| POST | `/user/respond_join` | Admin approves/rejects join request |

### CSV Bulk Import Format
```csv
first_name,last_name,email,member_id,phone
```

---

## Clubs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/clubs` | List all clubs |
| GET | `/clubs/new` | Create club (form) |
| POST | `/clubs/new` | Create club (submit) |
| GET | `/clubs/<id>/edit` | Edit club (form) |
| POST | `/clubs/<id>/edit` | Edit club (submit) |
| POST | `/clubs/<id>/delete` | Delete club |
| POST | `/clubs/<id>/request_home` | Request home club status |
| POST | `/clubs/respond_home_request` | Respond to home request |
| POST | `/clubs/respond_home_proposal` | Respond to home proposal |

---

## Contacts

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/contacts` | List all contacts |
| GET | `/contact/form` | Add contact (form) |
| POST | `/contact/form` | Add contact (submit) |
| GET | `/contact/form/<id>` | Edit contact (form) |
| POST | `/contact/form/<id>` | Edit contact (submit) |
| POST | `/contact/delete/<id>` | Delete contact |
| GET | `/contacts/search` | Search contacts |
| GET | `/contacts/cards` | View member cards |
| POST | `/contacts/merge` | Merge duplicate contacts |

---

## Agenda & Meetings

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/agenda` | View agenda builder |
| POST | `/agenda/create` | Create new agenda |
| POST | `/agenda/update` | Update agenda |
| GET | `/agenda/export/<id>` | Export agenda (PDF/CSV) |
| GET | `/agenda/ppt/<id>` | Generate PowerPoint |
| POST | `/agenda/delete/<id>` | Delete agenda item |
| POST | `/agenda/status/<id>` | Update meeting status |
| POST | `/agenda/sync_tally/<id>` | Sync with Tally |
| GET | `/api/data/all` | Get all meeting data |
| GET | `/api/agenda/get_logs/<id>` | Get agenda logs |

---

## Role Booking

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/booking` | Role booking dashboard |
| GET | `/booking/<meeting_id>` | Book roles for meeting |
| POST | `/booking/book` | Book a meeting role |

---

## Voting

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/voting` | Live voting dashboard |
| GET | `/voting/<meeting_id>` | Voting for specific meeting |
| POST | `/voting/vote` | Cast single vote |
| POST | `/voting/batch_vote` | Cast multiple votes |
| GET | `/voting/nps` | View NPS scores |
| GET | `/voting/nps/comments/<id>` | View NPS comments |

---

## Speech Logs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/speech_logs` | List all speech logs |
| GET | `/speech_logs/projects` | List all projects |
| GET | `/speech_log/details/<id>` | Speech detail view |
| POST | `/speech_log/update/<id>` | Update speech record |
| POST | `/speech_log/suspend/<id>` | Suspend speech |
| POST | `/speech_log/complete/<id>` | Mark speech complete |

---

## Achievements

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/achievements` | List all achievements |
| GET | `/achievement/form` | Add achievement (form) |
| POST | `/achievement/form` | Add achievement (submit) |
| GET | `/achievement/form/<id>` | Edit achievement (form) |
| POST | `/achievement/form/<id>` | Edit achievement (submit) |
| POST | `/achievement/delete/<id>` | Delete achievement |
| POST | `/achievements/record` | Record new achievement |
| POST | `/achievements/revoke` | Revoke achievement |
| GET | `/achievements/status` | View achievement status |

---

## Settings

### ExComM (Officers)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/settings` | Settings dashboard |
| POST | `/settings/excomm/add` | Add officer |
| POST | `/settings/excomm/update` | Update officer |
| POST | `/settings/excomm/delete/<id>` | Remove officer |

### Sessions
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/settings/sessions/add` | Add session template |
| POST | `/settings/sessions/update` | Update session |
| POST | `/settings/sessions/delete/<id>` | Delete session |
| POST | `/settings/sessions/delete-logs/<id>` | Delete session logs |

### Roles
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/settings/roles/add` | Add meeting role |
| POST | `/settings/roles/update` | Update role |
| POST | `/settings/roles/delete/<id>` | Delete role |
| POST | `/settings/roles/import` | Import roles |

### Tickets
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/settings/tickets/add` | Add ticket type |
| POST | `/settings/tickets/update` | Update ticket type |
| POST | `/settings/tickets/delete/<id>` | Delete ticket type |

### Permissions & Users
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/settings/users` | List users (API) |
| GET | `/api/permissions/matrix` | View permissions matrix |
| POST | `/api/permissions/update` | Update permissions |
| GET | `/api/audit-log` | View audit log |
| POST | `/api/user-roles/update` | Update user roles |

---

## Other Features

### Club Info
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/about_club` | View club info |
| POST | `/about_club/update` | Update club info |
| POST | `/about_club/upload_logo` | Upload club logo |

### Pathway Library
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/pathway_library` | View pathway library |
| POST | `/pathway_library/update_project/<id>` | Update project |

### Planner
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/planner` | Meeting planner |
| GET | `/api/meeting/<id>` | Get meeting details |
| POST | `/api/planner` | Create plan |
| PUT | `/api/planner/<id>` | Update plan |
| POST | `/api/planner/<id>/cancel` | Cancel plan |
| DELETE | `/api/planner/<id>` | Delete plan |

### Messages
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/messages` | View messages |
| POST | `/messages/send` | Send message |
| GET | `/messages/<id>/read` | Mark as read |
| POST | `/messages/<id>/delete` | Delete message |
| GET | `/api/messages/inbox` | Inbox |
| GET | `/api/messages/sent` | Sent messages |
| GET | `/api/messages/recipients` | Recipients list |
| GET | `/api/messages/unread-count` | Unread count |

### Roster
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Dashboard |
| GET | `/participation-trend` | Participation trends |
| GET | `/amount-trend` | Amount trends |
| POST | `/api/entry` | Add roster entry |
| GET | `/api/entry/<id>` | Get entry |
| PUT | `/api/entry/<id>` | Update entry |
| POST | `/api/entry/<id>/restore` | Restore entry |
| DELETE | `/api/entry/<id>` | Delete entry |

### Booking
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/booking` | Booking dashboard |
| GET | `/booking/<meeting_id>` | Booking for meeting |
| POST | `/booking/book` | Book role |

### Lucky Draw
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/lucky_draw` | Lucky draw |

### Calendar
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/calendar` | Calendar view |

### Tools
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/validator` | Validator tool |
| POST | `/validator` | Submit for validation |
| GET | `/validator/status/<task_id>` | Check validation status |
| GET | `/api/report-bug` | Report bug |

---

## Notes

- All POST endpoints that modify data require authentication
- Routes are defined in `app/*_routes.py` files
- API responses are typically JSON
- Error responses return appropriate HTTP status codes
