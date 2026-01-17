# Migration from user_roles to user_clubs

## Overview
Successfully migrated the role management system from using the `user_roles` table to the `user_clubs` table. This consolidates user-club-role relationships into a single table and fixes the authorization issue for sysadmin accounts.

## Changes Made

### 1. Database Schema Changes
- **Added foreign key** to `user_clubs.club_role_id` pointing to `auth_roles.id`
- **Dropped** the `user_roles` table
- **Migration**: `f12ff9454119_drop_user_roles_table.py`

### 2. Model Updates

#### `app/models/user_club.py`
- Added `ForeignKey` constraint to `club_role_id`
- Added `club_role` relationship to access the `Role` object

#### `app/models/user.py`
- Updated `roles` relationship to use `user_clubs` as secondary table
- Set `viewonly=True` since role assignment now requires a club_id

#### `app/models/role.py`
- Updated `users` relationship to use `user_clubs` as secondary table
- Set `viewonly=True` for consistency

#### `app/models/__init__.py`
- Removed import of `UserRoleAssociation`
- Removed export of `UserRoleAssociation` from `__all__`

#### Deleted Files
- `app/models/user_role.py` (no longer needed)

### 3. Code Updates

#### `app/users_routes.py`
- Updated `_create_or_update_user()` function to use `UserClub` instead of `UserRoleAssociation`
- Now assigns the highest role to all user's club memberships
- Creates `UserClub` records for new users with their assigned role

#### `app/settings_routes.py`
- Updated `update_user_roles()` API endpoint to use `UserClub`
- Assigns highest role from selected roles to all user's club memberships

#### `app/club_context.py`
- Updated `authorized_club_required` decorator to check `user_clubs` table
- **SysAdmin**: Can access ANY club (checks if they have SysAdmin role in ANY UserClub record)
- **ClubAdmin and others**: Must have a specific membership for the current club

### 4. Test Updates

#### `tests/test_permission_system.py`
- Updated `setup_permissions()` to create `UserClub` records instead of appending to `user.roles`
- Updated `test_user_multiple_roles_assignment()` to use `UserClub`
- Updated `test_multiple_roles_union()` to work with the new single-role-per-club system
- All 9 tests passing ✅

## How It Works Now

### Role Assignment
1. Each user can have ONE role per club (stored in `user_clubs.club_role_id`)
2. When assigning multiple roles, the system picks the highest-level role
3. The `User.roles` property still works but is read-only (viewonly relationship)

### Authorization
1. **SysAdmin**: Has access to ALL clubs (checked by finding ANY UserClub record with SysAdmin role)
2. **ClubAdmin**: Has access to clubs where they have a UserClub record
3. **Other roles**: Have access to clubs where they have a UserClub record

### Data Migration
- Existing data was migrated by copying the highest role from `user_roles` to `user_clubs.club_role_id`
- User 1 (sysadmin) now has `club_role_id=1` (SysAdmin) in their UserClub record

## Benefits
1. **Simplified schema**: One table (`user_clubs`) instead of two (`user_roles` + `user_clubs`)
2. **Better multi-club support**: Role is tied to club membership
3. **Fixed authorization**: SysAdmin can now access all clubs correctly
4. **Cleaner code**: Less duplication in role management logic

## Backward Compatibility
- The `User.roles` property still works (returns roles from user_clubs)
- The `User.has_role()` and `User.has_permission()` methods work as before
- Existing code that reads roles continues to work

## Testing
- All permission system tests passing (9/9)
- Verified SysAdmin can access any club
- Verified regular users need club membership for access
