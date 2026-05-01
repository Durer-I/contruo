"""AI Auto-Takeoff Stage 1 + 2 schema (Sprint AI-02)

- Widens ``ai_runs.status`` from VARCHAR(20) to VARCHAR(40) to fit
  ``'awaiting_title_block'`` (and any future per-stage pause states such as
  ``awaiting_legend_confirmation``). Existing values are unchanged.
- Adds title-block detection columns to ``plans``:
    * ``title_block_bbox`` JSONB -- ``{"x0", "y0", "x1", "y1"}`` in PDF user-space
      points; null until Stage 1 detects (or the user manually confirms).
    * ``title_block_confidence`` FLOAT -- the heuristic's confidence (0.0-1.0).
    * ``title_block_source`` VARCHAR(20) -- ``'auto' | 'manual' | 'vision'``.
- No new RLS policies: existing ``plans`` and ``ai_runs`` policies cover the
  new columns.
- These columns are intentionally NOT exposed via ``PlanResponse`` in AI-02 --
  the bbox is surfaced only via ``GET /ai/runs/{rid}`` during the awaiting
  pause and via the confirm endpoint. Future sprints can add them to
  ``PlanResponse.from_model`` as a 3-line additive change.

Revision ID: 014_ai_title_block_and_pause
Revises: 013_ai_runs_layer_n_extractions
Create Date: 2026-04-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "014_ai_title_block_and_pause"
down_revision: Union[str, None] = "013_ai_runs_layer_n_extractions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── ai_runs.status: widen for pause states ──────────────────────────
    # Postgres preserves data on a VARCHAR widen; no USING clause needed.
    op.alter_column(
        "ai_runs",
        "status",
        existing_type=sa.String(20),
        type_=sa.String(40),
        existing_nullable=False,
        existing_server_default=sa.text("'queued'::character varying"),
    )

    # ── plans: title-block detection columns ────────────────────────────
    op.add_column(
        "plans",
        sa.Column(
            "title_block_bbox",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "plans",
        sa.Column("title_block_confidence", sa.Float(), nullable=True),
    )
    # 'auto' (heuristic >= threshold) | 'manual' (user confirmed/adjusted) |
    # 'vision' (reserved for future vision-assisted detection).
    op.add_column(
        "plans",
        sa.Column("title_block_source", sa.String(20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("plans", "title_block_source")
    op.drop_column("plans", "title_block_confidence")
    op.drop_column("plans", "title_block_bbox")

    # Narrow ``status`` back to VARCHAR(20). Any rows still in pause states
    # would fail to fit -- clear them to ``failed`` first so the downgrade
    # never blocks. This is destructive on purpose; downgrades from AI-02
    # to AI-01 are dev-only escape hatches.
    op.execute(
        """
        UPDATE ai_runs
           SET status = 'failed',
               error_message = COALESCE(error_message, '') ||
                               ' (downgraded from AI-02 pause state)'
         WHERE status NOT IN ('queued', 'running', 'completed', 'failed', 'cancelled')
        """
    )
    op.alter_column(
        "ai_runs",
        "status",
        existing_type=sa.String(40),
        type_=sa.String(20),
        existing_nullable=False,
        existing_server_default=sa.text("'queued'::character varying"),
    )
