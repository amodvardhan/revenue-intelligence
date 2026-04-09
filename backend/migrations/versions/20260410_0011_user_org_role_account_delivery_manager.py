"""Add account_manager and delivery_manager organization roles."""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260410_0011"
down_revision: Union[str, None] = "20260409_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE user_org_role DROP CONSTRAINT IF EXISTS ck_user_org_role_role;")
    op.execute(
        """
ALTER TABLE user_org_role ADD CONSTRAINT ck_user_org_role_role CHECK (role IN (
    'admin',
    'cxo',
    'bu_head',
    'finance',
    'viewer',
    'it_admin',
    'account_manager',
    'delivery_manager'
));
"""
    )


def downgrade() -> None:
    op.execute("ALTER TABLE user_org_role DROP CONSTRAINT IF EXISTS ck_user_org_role_role;")
    op.execute(
        """
ALTER TABLE user_org_role ADD CONSTRAINT ck_user_org_role_role CHECK (role IN (
    'admin', 'cxo', 'bu_head', 'finance', 'viewer', 'it_admin'
));
"""
    )
