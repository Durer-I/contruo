"""Performance + concurrency upgrades.

- Composite indexes on ``measurements`` to match hottest query patterns
  (``(org_id, project_id)`` and ``(org_id, project_id, sheet_id, created_at)``).
- ``measurements.version`` integer for optimistic locking via ``If-Match`` headers.
- ``pg_trgm`` extension + GIN index on ``sheets.text_content`` for full-text-ish
  search (currently linear ILIKE).
"""

from alembic import op
import sqlalchemy as sa


revision = "012_perf_indexes_and_versioning"
down_revision = "011_plan_processing_substep"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Composite indexes — Postgres can usually combine single-column indexes, but
    # composites on (org_id, project_id[, sheet_id]) align with our exact filters
    # plus the order_by on created_at and avoid bitmap-merge overhead at scale.
    op.create_index(
        "ix_measurements_org_project",
        "measurements",
        ["org_id", "project_id"],
    )
    op.create_index(
        "ix_measurements_org_project_sheet_created",
        "measurements",
        ["org_id", "project_id", "sheet_id", "created_at"],
    )

    # Optimistic locking column — defaults to 1 for existing rows so first PATCH
    # without an If-Match header can be ignored at the route layer (we treat
    # missing If-Match as "client doesn't care" for backwards compat).
    op.add_column(
        "measurements",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.alter_column("measurements", "version", server_default=None)

    # Sheet text search — pg_trgm gives us substring/ILIKE in O(log n) via GIN.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sheets_text_content_trgm "
        "ON sheets USING GIN (text_content gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_sheets_text_content_trgm")
    op.drop_column("measurements", "version")
    op.drop_index("ix_measurements_org_project_sheet_created", table_name="measurements")
    op.drop_index("ix_measurements_org_project", table_name="measurements")
