"""Legend storage path helpers (Sprint AI-03)."""

from __future__ import annotations

import uuid

from app.utils import legend_storage


def test_compute_template_hash_is_stable():
    h1 = legend_storage.compute_template_hash(b"abc")
    h2 = legend_storage.compute_template_hash(b"abc")
    assert h1 == h2
    assert len(h1) == 64
    assert h1 != legend_storage.compute_template_hash(b"abd")


def test_variant_filename_format():
    name = legend_storage.variant_filename(
        template_hash="a" * 64, scale=1.0, rotation=0
    )
    assert name == ("a" * 64) + "_s1.00_r000.png"

    name2 = legend_storage.variant_filename(
        template_hash="b" * 64, scale=0.7, rotation=270
    )
    assert name2 == ("b" * 64) + "_s0.70_r270.png"


def test_variant_storage_path_is_org_scoped():
    org_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    plan_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    path = legend_storage.variant_storage_path(
        org_id, plan_id, template_hash="a" * 64, scale=1.0, rotation=0
    )
    assert path == (
        f"{org_id}/legends/{plan_id}/" + ("a" * 64) + "_s1.00_r000.png"
    )


def test_safe_label_slug_handles_empty_and_special_chars():
    assert legend_storage.safe_label_slug("") == "unlabeled"
    assert legend_storage.safe_label_slug("   ") == "unlabeled"
    assert legend_storage.safe_label_slug("AC-1 (PUMP)") == "AC-1_PUMP"
    assert legend_storage.safe_label_slug("door & window") == "door_window"


def test_safe_label_slug_truncates():
    long = "A" * 100
    assert legend_storage.safe_label_slug(long, max_len=10) == "A" * 10
