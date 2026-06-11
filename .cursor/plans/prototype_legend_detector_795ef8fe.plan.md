---
name: Prototype legend detector
overview: Replace production legend detection in `ai_legend_detector.py` with the exact algorithm from `AI/controller/legends.py` (right-adjacent labels only, tolerance=2, min_size=16, no max-size cap, no multi-direction or confidence gating). Map merged results to existing `LegendCandidate` + persistence unchanged. Bump cache version and adjust tests that enforced removed behavior.
todos:
  - id: rewrite-detector
    content: Replace ai_legend_detector.py with prototype algorithm; map merged_results to LegendCandidate + y0/y1; bump extraction_method; remove old filters/helpers
    status: cancelled
  - id: config-readme
    content: Default ai_legend_merge_tolerance=2.0; README note on unused legend env knobs
    status: cancelled
  - id: cache-version
    content: Bump SCHEDULES_LEGENDS_VERSION to v2 in ai_pipeline.py
    status: cancelled
  - id: tests
    content: "Update test_ai_legend_detector: drop above/huge tests; fix confidence assertions"
    status: cancelled
  - id: debug-dedupe
    content: If debug dump exists, align with shared helpers or remove duplicate
    status: cancelled
isProject: false
---

# Prototype-only legend detection

## Goal

Use the **same logic as** [`AI/controller/legends.py`](AI/controller/legends.py) (group rects by rounded `(rx0, rx1)`, dominant `(rwidth, rheight)`, skip `has_text_inside`, `get_adjacent_text` to the **right** only, `label_map` → `merge_rects`) for every keyword-matched legend sheet. **Do not change** [`ai_legend_extractor.py`](backend/app/services/ai_legend_extractor.py) persistence (crops, Storage, `extracted_legends` / variants) or [`ai_sheet_filter.py`](backend/app/services/ai_sheet_filter.py) sheet selection.

## Coordinate bridge (minimal change)

Prototype `merge_rects` returns `{x0, x1, top, bottom}` (pdfplumber). The extractor already expects `bbox_pdf` as `{x0, y0, x1, y1}` with **`y0` = top edge, `y1` = bottom edge** — same mapping the current [`_merge_rects`](backend/app/services/ai_legend_detector.py) uses for PyMuPDF clips. For each merged label entry:

```python
bbox_pdf = {"x0": m["x0"], "y0": m["top"], "x1": m["x1"], "y1": m["bottom"]}
```

## Implementation steps

1. **Rewrite [`backend/app/services/ai_legend_detector.py`](backend/app/services/ai_legend_detector.py)**

   - Keep: `LegendCandidate` dataclass, `serialize_candidates` / `deserialize_candidates` (cache + internal API).
   - Replace `detect_legend_symbols` body with the prototype pipeline inlined or factored into small helpers matching the script verbatim:
     - `has_text_inside`, `get_adjacent_text`, `merge_rects` (same signatures/behavior as the prototype).
     - Main loop: `tolerance` default **2** (match script; wire to existing `ai_legend_merge_tolerance` **or** hardcode 2 — recommend **default config `ai_legend_merge_tolerance: float = 2.0`** so env can still tune without reintroducing prod-only logic).
     - `min_size` **16** fixed (match script); **remove** `ai_legend_symbol_min_pts` / `ai_legend_symbol_max_pts` filtering from this module (prototype has no max).
     - **Remove**: multi-direction `_find_adjacent_label`, `_score_confidence`, and the post-filter `confidence < ai_legend_min_confidence` (or keep filter but set every candidate `confidence = 1.0` so nothing drops — simpler to remove filter and set `confidence=1.0`, `extraction_method="pdfplumber_rects_proto"`).
   - **`sibling_count`**: number of raw rects appended to `label_map[text]` before merge (same semantics tests already expect for the merge case).
   - Delete dead code (hundreds of lines of old detector) to avoid drift.

2. **Config ([`backend/app/config.py`](backend/app/config.py))**

   - Set **`ai_legend_merge_tolerance` default to `2.0`** (align with prototype; document that 5.0 was the old grouped-rect variant).
   - Optionally deprecate or leave unused: `ai_legend_min_confidence`, `ai_legend_symbol_min_pts`, `ai_legend_symbol_max_pts` (no longer read by detector). Prefer **leaving env vars** but stopping use in detector to avoid breaking `.env`; note in [`backend/README.md`](backend/README.md) that legend detection no longer applies max-size / min-confidence filters.

3. **Cache invalidation ([`backend/app/tasks/ai_pipeline.py`](backend/app/tasks/ai_pipeline.py))**

   - Bump **`SCHEDULES_LEGENDS_VERSION`** from `"v1"` to **`"v2"`** so `legends_v1` cache keys with `model_version=detector:v2` force re-extraction for existing plans.

4. **Tests ([`backend/tests/unit/test_ai_legend_detector.py`](backend/tests/unit/test_ai_legend_detector.py))**

   - **Remove or replace** `test_label_above_direction` — prototype has **no** above-label path; with pure prototype this scenario returns **no** candidates (unless you explicitly keep a non-prod extension, which you are not).
   - **Remove or replace** `test_size_filter_rejects_huge_rects` — prototype does **not** cap rect size; either delete or change to assert giant rects can still be detected (usually undesirable); **deleting** is cleaner.
   - Adjust any assertions that depended on **confidence scoring** (e.g. weak-sibling penalties) if all confidences become `1.0`.
   - Keep: column + right-label tests, text-inside skip, tiny rect skip (min 16), merge duplicate labels, serialize round-trip.

5. **Optional cleanup**

   - If a **debug-only** `legend_prototype_dump` module was added earlier, remove duplication or have it **import** the same helpers as the detector to avoid two sources of truth.

## Out of scope (per your request)

- Changing keyword lists or schedule extraction.
- GPT cleanup from the prototype script (still commented there).
- New UI.

## Risk note

Merging all rects that share the **same adjacent text string** into one bbox is **inherited from the prototype** — same as today’s production merge path. If two symbols share one label string, the crop will span both; acceptable for “match prototype as-is.”
