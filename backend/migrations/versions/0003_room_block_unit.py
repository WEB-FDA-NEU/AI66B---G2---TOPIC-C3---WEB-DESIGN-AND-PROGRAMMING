"""Add optional unit scope without rewriting old blocks or reservation history."""

import sqlalchemy as sa
from alembic import op

revision = "0003_block_unit"
down_revision = "0002_luxstay"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name == "sqlite":
        # Native additive ALTER avoids rebuilding a parent table referenced by RoomNight.
        op.execute(
            "ALTER TABLE room_blocks ADD COLUMN unit INTEGER CONSTRAINT ck_room_blocks_unit_range CHECK (unit IS NULL OR (unit >= 1 AND unit <= 100))"
        )
    else:
        op.add_column("room_blocks", sa.Column("unit", sa.Integer(), nullable=True))
        op.create_check_constraint(
            op.f("ck_room_blocks_unit_range"), "room_blocks", "unit IS NULL OR (unit >= 1 AND unit <= 100)"
        )


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; restore a verified backup instead")
