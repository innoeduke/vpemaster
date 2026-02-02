# User and Contact Management Simplification

## Summary of Changes

### 1. Simplified User Creation
**Before**: Users could optionally be linked to contacts via a search box or create new contact checkbox  
**After**: Every new user automatically gets a new contact created and linked

**Changes Made**:
- ✅ Removed contact search box from user form template
- ✅ Removed "+" checkbox for creating new contact
- ✅ Updated `_create_or_update_user()` to always create a contact for new users
- ✅ Removed contact search JavaScript logic
- ✅ Contact is automatically created with:
  - Name = Username
  - Email = User's email
  - Type = 'Member'
  - Linked to current club via ContactClub

### 2. User Deletion Cleanup
**Before**: Deleting a user left the linked contact orphaned  
**After**: Deleting a user also deletes the linked contact

**Changes Made**:
- ✅ Updated `delete_user()` function to delete linked contact before deleting user
- ✅ Cascade delete configured on UserClub relationship

### 3. User Search Feature
**Added**: Search box to find existing users when adding to a club

**Features**:
- Search by username, email, phone, or contact name
- Shows up to 10 matching results
- Click on result to edit that user (add to current club)

### 4. Role Management Updates
**Completed Earlier**:
- ✅ Migrated from `user_roles` to `user_clubs` table
- ✅ Dropped `user_roles` table
- ✅ SysAdmin and ClubAdmin excluded from permissions matrix
- ✅ Guest role still available for assignment

## Remaining Tasks

### 3. Contact Page Modifications (TODO)
Need to update contacts page to:
- Allow adding/deleting only Guest contacts
- Remove Type field (all contacts from contact page will be Guest type)
- User-linked contacts (Members) managed only through user management

## Database Schema

**Users** → **Contacts** (1:1, auto-created)  
**Users** → **UserClubs** (1:many, with roles)  
**Contacts** → **ContactClubs** (many:many, club membership)  

## Workflow

### Adding a New User
1. Go to Settings → Users → Add User
2. (Optional) Search for existing user to add to club
3. Fill in username, email, password
4. Select roles (Staff, User, Guest - not SysAdmin/ClubAdmin)
5. Submit → Contact auto-created and linked

### Deleting a User
1. Delete user → Contact automatically deleted too

### Managing Guests (TODO - Next Step)
1. Go to Contacts page
2. Add/delete guest contacts only
3. No type field needed
