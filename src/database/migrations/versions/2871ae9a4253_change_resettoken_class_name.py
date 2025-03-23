"""Change resettoken class name

Revision ID: 2871ae9a4253
Revises: 6bddba355931
Create Date: 2025-03-23 17:14:33.220149

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2871ae9a4253'
down_revision: Union[str, None] = '6bddba355931'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
