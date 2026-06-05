"""Association table for Role-Permission many-to-many relationship.

Per-club: each (role, permission) pair is scoped to a specific club via
club_id, so different clubs can have different permission matrices for the
same role. See docs/access_matrix.md.
"""
from .base import db


class RolePermission(db.Model):
    __tablename__ = 'role_permissions'

    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('auth_roles.id', ondelete='CASCADE'), nullable=False)
    permission_id = db.Column(db.Integer, db.ForeignKey('permissions.id', ondelete='CASCADE'), nullable=False)
    # Nullable in the model so that test fixtures (which use db.create_all()
    # and may not always set club_id) keep working. The Alembic migration
    # enforces NOT NULL at the DB level for prod, after backfilling all
    # active clubs. App code (update_permission_matrix, etc.) always sets it.
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id', ondelete='CASCADE'), nullable=True, index=True)

    # Unique constraint on (role_id, permission_id, club_id) is added by the
    # Alembic migration (replaces the old (role_id, permission_id) constraint).
    __table_args__ = ()

    def __repr__(self):
        return f'<RolePermission role_id={self.role_id} permission_id={self.permission_id} club_id={self.club_id}>'
