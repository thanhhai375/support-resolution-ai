
"""add RBAC roles

Revision ID: 4ab674d82d22
Revises: e153192b44d0
Create Date: 2026-11-19 17:48:13.819246+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4ab674d82d22'
down_revision: Union[str, None] = 'e153192b44d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass