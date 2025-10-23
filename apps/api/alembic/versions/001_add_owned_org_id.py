"""add owned_org_id to users

Revision ID: 001_add_owned_org_id
Revises: 
Create Date: 2025-10-22 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_add_owned_org_id'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add owned_org_id column to users table for 1:1 user-organization ownership."""
    
    # Add owned_org_id column
    op.add_column('users', 
        sa.Column('owned_org_id', postgresql.UUID(as_uuid=True), nullable=True)
    )
    
    # Add foreign key constraint
    op.create_foreign_key(
        'fk_users_owned_org',
        'users', 'organizations',
        ['owned_org_id'], ['id'],
        ondelete='CASCADE'
    )
    
    # Add unique constraint (one organization per owner)
    op.create_unique_constraint(
        'uq_users_owned_org',
        'users',
        ['owned_org_id']
    )
    
    # Create index for performance
    op.create_index(
        'ix_users_owned_org_id',
        'users',
        ['owned_org_id']
    )


def downgrade() -> None:
    """Remove owned_org_id column and constraints."""
    
    # Drop index
    op.drop_index('ix_users_owned_org_id', table_name='users')
    
    # Drop unique constraint
    op.drop_constraint('uq_users_owned_org', 'users', type_='unique')
    
    # Drop foreign key
    op.drop_constraint('fk_users_owned_org', 'users', type_='foreignkey')
    
    # Drop column
    op.drop_column('users', 'owned_org_id')
