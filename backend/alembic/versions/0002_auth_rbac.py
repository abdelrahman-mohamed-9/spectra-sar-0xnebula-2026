"""Add user identities and per-project membership roles.

Revision ID: 0002_auth_rbac
Revises: 0001_postgis_initial
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision='0002_auth_rbac'
down_revision='0001_postgis_initial'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('users',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True,server_default=sa.text('gen_random_uuid()')),
        sa.Column('email',sa.String(254),nullable=False),
        sa.Column('password_hash',sa.Text(),nullable=False),
        sa.Column('is_active',sa.Boolean(),nullable=False,server_default=sa.text('true')),
        sa.Column('is_platform_admin',sa.Boolean(),nullable=False,server_default=sa.text('false')),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.UniqueConstraint('email',name='uq_users_email'))
    op.create_table('project_memberships',
        sa.Column('project_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('projects.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('role',sa.String(16),nullable=False),
        sa.CheckConstraint("role IN ('viewer','analyst','editor','owner')",name='ck_membership_role'))
    op.create_index('ix_membership_user','project_memberships',['user_id'])

def downgrade():
    op.drop_index('ix_membership_user',table_name='project_memberships')
    op.drop_table('project_memberships')
    op.drop_table('users')
