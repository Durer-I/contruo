"""AI Auto-Takeoff foundations (Sprint AI-01)

- ``ai_runs``: one row per pipeline invocation (status, model snapshot, cost,
  per-stage timings in ``summary_jsonb``).
- ``ai_layer_items``: per-detection geometry with confidence + status. Real
  ``measurements`` are still the source of truth; layer items become measurements
  on accept (auto or user).
- ``extracted_schedules`` / ``extracted_legends``: provenance for Stage 3 outputs
  (schedules tables + legend symbol crops). Empty until AI-03.
- ``ai_stage_cache``: stage output cache keyed by ``(content_hash, stage,
  model_version)``. Re-runs on unchanged sheets short-circuit.
- New columns on ``measurements`` / ``conditions`` / ``sheets`` for AI provenance
  and sheet classification (filled in by AI-02+; defaults preserve existing rows).

RLS follows the existing pattern: ``org_id = (SELECT org_id FROM users WHERE id = auth.uid())``.

Revision ID: 013
Revises: 012_perf_indexes_and_versioning
Create Date: 2026-04-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "013_ai_runs_layer_n_extractions"
down_revision: Union[str, None] = "012_perf_indexes_and_versioning"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── ai_runs ─────────────────────────────────────────────────────
    op.create_table(
        "ai_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("triggered_by", postgresql.UUID(as_uuid=True), nullable=False),
        # 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
        sa.Column("status", sa.String(20), server_default="queued", nullable=False),
        sa.Column("scope", sa.String(20), server_default="full_plan", nullable=False),
        # Snapshot of the vision/embedding/llm provider+model at run start so a
        # later cache hit / re-run can detect drift.
        sa.Column(
            "model_versions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cost_cents", sa.Integer(), server_default="0", nullable=False),
        sa.Column("tokens_used", sa.Integer(), server_default="0", nullable=False),
        sa.Column("items_total", sa.Integer(), server_default="0", nullable=False),
        sa.Column("items_accepted_auto", sa.Integer(), server_default="0", nullable=False),
        sa.Column("items_pending", sa.Integer(), server_default="0", nullable=False),
        sa.Column("items_low_confidence", sa.Integer(), server_default="0", nullable=False),
        # Per-stage timings, per-condition counts, divergences, errors. Updated
        # incrementally by each stage task.
        sa.Column(
            "summary_jsonb",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["triggered_by"], ["users.id"]),
    )
    op.create_index("ix_ai_runs_org_id", "ai_runs", ["org_id"])
    op.create_index("ix_ai_runs_project_id", "ai_runs", ["project_id"])
    op.create_index("ix_ai_runs_plan_id", "ai_runs", ["plan_id"])
    # Hot path: "is there an active run on this plan right now?" + 24h cost rollup.
    op.create_index(
        "ix_ai_runs_org_status_created",
        "ai_runs",
        ["org_id", "status", "created_at"],
    )

    # ── ai_layer_items ─────────────────────────────────────────────
    op.create_table(
        "ai_layer_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ai_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sheet_id", postgresql.UUID(as_uuid=True), nullable=False),
        # Nullable until the resolver (AI-04) runs. Until then a layer item is
        # a raw geometric primitive with no condition assigned yet.
        sa.Column("condition_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("measurement_type", sa.String(20), nullable=False),
        # Geometry in PDF user space points (matches measurements.geometry shape).
        sa.Column("geometry", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        # Which pipeline stage produced this item: 'title_block' | 'classification'
        # | 'schedules_legends' | 'element_detection' | 'resolver'.
        sa.Column("source_stage", sa.String(40), nullable=False),
        # 'pending' | 'accepted_auto' | 'accepted_user' | 'rejected'
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        # Free-form per-item metadata: matched_legend_label, source_template_id, etc.
        sa.Column(
            "metadata_jsonb",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        # When status=accepted_*, the resulting measurement row id (denormalized
        # so the layer panel can highlight without a join).
        sa.Column("accepted_measurement_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["ai_run_id"], ["ai_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sheet_id"], ["sheets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["condition_id"], ["conditions.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_ai_layer_items_org_id", "ai_layer_items", ["org_id"])
    op.create_index("ix_ai_layer_items_ai_run_id", "ai_layer_items", ["ai_run_id"])
    op.create_index("ix_ai_layer_items_sheet_id", "ai_layer_items", ["sheet_id"])
    # AI-05 review panel: "show all pending items on this sheet".
    op.create_index(
        "ix_ai_layer_items_sheet_status",
        "ai_layer_items",
        ["sheet_id", "status"],
    )

    # ── extracted_schedules ────────────────────────────────────────
    op.create_table(
        "extracted_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ai_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sheet_id", postgresql.UUID(as_uuid=True), nullable=False),
        # PDF-points bbox: {"x0": ..., "y0": ..., "x1": ..., "y1": ...}
        sa.Column("bbox_pdf", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        # Index of the column used as the tag key (e.g. "MARK"/"TYPE"). Heuristic-first.
        sa.Column("tag_column_index", sa.Integer(), nullable=True),
        # Full table data: {"headers": [...], "rows": [[...], ...]}
        sa.Column("extracted_table_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        # 'pdfplumber_lines' | 'pdfplumber_text' | 'vision'
        sa.Column("extraction_method", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["ai_run_id"], ["ai_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sheet_id"], ["sheets.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_extracted_schedules_org_id", "extracted_schedules", ["org_id"])
    op.create_index("ix_extracted_schedules_ai_run_id", "extracted_schedules", ["ai_run_id"])
    op.create_index("ix_extracted_schedules_sheet_id", "extracted_schedules", ["sheet_id"])

    # ── extracted_legends ──────────────────────────────────────────
    op.create_table(
        "extracted_legends",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ai_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sheet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bbox_pdf", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        # Supabase Storage path: legends/{plan_id}/{legend_label}.png
        sa.Column("template_storage_path", sa.Text(), nullable=False),
        # SHA-256 of the cropped template bytes for cache invalidation.
        sa.Column("template_hash", sa.String(64), nullable=False),
        # 'vector' | 'raster' | 'vision'
        sa.Column("extraction_method", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["ai_run_id"], ["ai_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sheet_id"], ["sheets.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_extracted_legends_org_id", "extracted_legends", ["org_id"])
    op.create_index("ix_extracted_legends_ai_run_id", "extracted_legends", ["ai_run_id"])
    op.create_index("ix_extracted_legends_sheet_id", "extracted_legends", ["sheet_id"])

    # ── ai_stage_cache ─────────────────────────────────────────────
    # Note: ``org_id`` is included for RLS consistency, but cache hits are scoped
    # to ``(content_hash, stage, model_version)`` -- two orgs uploading the same
    # PDF still get isolated cache rows because the org RLS gates lookups.
    op.create_table(
        "ai_stage_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("stage", sa.String(40), nullable=False),
        sa.Column("model_version", sa.String(120), nullable=False),
        sa.Column("value_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("hit_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.UniqueConstraint(
            "org_id",
            "content_hash",
            "stage",
            "model_version",
            name="uq_ai_stage_cache_key",
        ),
    )
    op.create_index("ix_ai_stage_cache_org_id", "ai_stage_cache", ["org_id"])

    # ── measurements: provenance ──────────────────────────────────
    op.add_column(
        "measurements",
        sa.Column("source", sa.String(20), server_default="user", nullable=False),
    )
    op.add_column(
        "measurements",
        sa.Column("ai_run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_measurements_ai_run_id",
        "measurements",
        "ai_runs",
        ["ai_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # "Show me everything created by Run #7" filter on the quantities panel.
    op.create_index("ix_measurements_ai_run_id", "measurements", ["ai_run_id"])

    # ── conditions: provenance ────────────────────────────────────
    op.add_column(
        "conditions",
        sa.Column("source", sa.String(20), server_default="user", nullable=False),
    )
    op.add_column(
        "conditions",
        sa.Column("source_template_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "conditions",
        sa.Column("source_ai_run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_conditions_source_template_id",
        "conditions",
        "condition_templates",
        ["source_template_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_conditions_source_ai_run_id",
        "conditions",
        "ai_runs",
        ["source_ai_run_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ── sheets: classification (filled in by AI-02) ───────────────
    # 'architectural' | 'structural' | 'mechanical' | 'plumbing' | 'electrical'
    # | 'fire_protection' | 'civil' | 'other'
    op.add_column(
        "sheets",
        sa.Column("discipline", sa.String(40), nullable=True),
    )
    # 'cover' | 'index' | 'plan' | 'schedule' | 'legend' | 'detail' | 'spec'
    # | 'elevation' | 'section' | 'other'
    op.add_column(
        "sheets",
        sa.Column("sheet_type", sa.String(40), nullable=True),
    )
    op.add_column(
        "sheets",
        sa.Column("classification_confidence", sa.Float(), nullable=True),
    )
    # 'lexical' | 'vision'
    op.add_column(
        "sheets",
        sa.Column("classification_method", sa.String(20), nullable=True),
    )

    # ── RLS ───────────────────────────────────────────────────────
    op.execute("ALTER TABLE ai_runs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ai_layer_items ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE extracted_schedules ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE extracted_legends ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ai_stage_cache ENABLE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY "Users can only access their org's ai_runs"
            ON ai_runs FOR ALL
            USING (org_id = (SELECT org_id FROM users WHERE id = auth.uid()))
        """
    )
    op.execute(
        """
        CREATE POLICY "Users can only access their org's ai_layer_items"
            ON ai_layer_items FOR ALL
            USING (org_id = (SELECT org_id FROM users WHERE id = auth.uid()))
        """
    )
    op.execute(
        """
        CREATE POLICY "Users can only access their org's extracted_schedules"
            ON extracted_schedules FOR ALL
            USING (org_id = (SELECT org_id FROM users WHERE id = auth.uid()))
        """
    )
    op.execute(
        """
        CREATE POLICY "Users can only access their org's extracted_legends"
            ON extracted_legends FOR ALL
            USING (org_id = (SELECT org_id FROM users WHERE id = auth.uid()))
        """
    )
    op.execute(
        """
        CREATE POLICY "Users can only access their org's ai_stage_cache"
            ON ai_stage_cache FOR ALL
            USING (org_id = (SELECT org_id FROM users WHERE id = auth.uid()))
        """
    )


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS "Users can only access their org\'s ai_stage_cache" ON ai_stage_cache')
    op.execute('DROP POLICY IF EXISTS "Users can only access their org\'s extracted_legends" ON extracted_legends')
    op.execute('DROP POLICY IF EXISTS "Users can only access their org\'s extracted_schedules" ON extracted_schedules')
    op.execute('DROP POLICY IF EXISTS "Users can only access their org\'s ai_layer_items" ON ai_layer_items')
    op.execute('DROP POLICY IF EXISTS "Users can only access their org\'s ai_runs" ON ai_runs')

    op.drop_column("sheets", "classification_method")
    op.drop_column("sheets", "classification_confidence")
    op.drop_column("sheets", "sheet_type")
    op.drop_column("sheets", "discipline")

    op.drop_constraint("fk_conditions_source_ai_run_id", "conditions", type_="foreignkey")
    op.drop_constraint("fk_conditions_source_template_id", "conditions", type_="foreignkey")
    op.drop_column("conditions", "source_ai_run_id")
    op.drop_column("conditions", "source_template_id")
    op.drop_column("conditions", "source")

    op.drop_index("ix_measurements_ai_run_id", table_name="measurements")
    op.drop_constraint("fk_measurements_ai_run_id", "measurements", type_="foreignkey")
    op.drop_column("measurements", "ai_run_id")
    op.drop_column("measurements", "source")

    op.drop_table("ai_stage_cache")
    op.drop_table("extracted_legends")
    op.drop_table("extracted_schedules")
    op.drop_table("ai_layer_items")
    op.drop_table("ai_runs")
