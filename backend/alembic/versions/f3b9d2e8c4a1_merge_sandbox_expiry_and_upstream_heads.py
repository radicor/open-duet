"""merge our sandbox-expiry head with the upstream feature heads

Radicor fork head e7b3c1a5d942 (index user_sandbox for expiry) met the
upstream tree after its own merge migration 32f1a61f1173 (team chief and
memory heads). No schema conflict: this migration only joins the branches so
`alembic upgrade head` has a single head again.

Revision ID: f3b9d2e8c4a1
Revises: e7b3c1a5d942, 32f1a61f1173
Create Date: 2026-10-23 22:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3b9d2e8c4a1'
down_revision: Union[str, Sequence[str], None] = ('e7b3c1a5d942', '32f1a61f1173')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
