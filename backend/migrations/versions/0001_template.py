"""Non-destructive baseline of the original users/items template.

Recognizes the exact old table shape, preserving all rows. Unknown databases
are refused instead of stamped or overwritten. Back up before upgrading.
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_template"
down_revision = None
branch_labels = depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names()) - {"alembic_version"}
    if tables:
        expected = {
            "users": {"id", "email", "password_hash", "display_name", "phone", "role", "created_at"},
            "items": {"id", "title", "description", "price", "cover_url", "status", "created_at", "owner_id"},
        }
        if tables != set(expected) or any(
            {c["name"] for c in inspector.get_columns(table)} != cols for table, cols in expected.items()
        ):
            raise RuntimeError(
                "Unrecognized existing database; back up and prepare an explicit migration. No data was overwritten."
            )
        for table in ("users", "items"):
            columns = {column["name"]: column for column in inspector.get_columns(table)}
            if not isinstance(columns["id"]["type"], sa.Integer) or inspector.get_pk_constraint(table)[
                "constrained_columns"
            ] != ["id"]:
                raise RuntimeError(
                    "Legacy ID/primary-key shape is unsupported; prepare an explicit migration"
                )
        unique_email = any(
            index.get("unique") and index["column_names"] == ["email"]
            for index in inspector.get_indexes("users")
        ) or any(
            constraint["column_names"] == ["email"]
            for constraint in inspector.get_unique_constraints("users")
        )
        if not unique_email:
            raise RuntimeError("Legacy email uniqueness is missing; prepare an explicit migration")
        owner_fk = any(
            fk["constrained_columns"] == ["owner_id"]
            and fk["referred_table"] == "users"
            and fk["referred_columns"] == ["id"]
            for fk in inspector.get_foreign_keys("items")
        )
        if not owner_fk:
            raise RuntimeError("Legacy ownership foreign key is missing; prepare an explicit migration")
        return
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table(
        "items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("cover_url", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
    )
    for column in ["title", "status", "created_at"]:
        op.create_index("ix_items_" + column, "items", [column])


def downgrade():
    raise RuntimeError("Destructive baseline downgrade is disabled; restore an explicit verified backup")
