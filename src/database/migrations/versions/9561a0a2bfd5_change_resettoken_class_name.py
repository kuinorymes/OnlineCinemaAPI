"""Change resettoken class name

Revision ID: 9561a0a2bfd5
Revises: 2871ae9a4253
Create Date: 2025-03-23 17:16:01.124255

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9561a0a2bfd5'
down_revision: Union[str, None] = '2871ae9a4253'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
