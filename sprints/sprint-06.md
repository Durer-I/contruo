# Sprint 06: Scale Calibration & Text Search

> **Phase:** 2 - Plan Viewing
> **Duration:** 2 weeks
> **Status:** Complete
> **Depends On:** Sprint 05

## Sprint Goal

Implement scale calibration (manual + auto-detect) and full-text search within plans. At the end of this sprint, users can calibrate the scale on each sheet so measurements are accurate, and search for text across all sheets.

---

## Tasks

### 1. Manual Scale Calibration
- [x] Create scale calibration tool (activated via toolbar button or `S` shortcut)
- [x] User draws a line between two known points on the plan
- [x] Dialog prompts for real-world distance and unit (e.g., "10 feet")
- [x] System calculates pixels-per-unit ratio and stores per sheet
- [x] Visual indicator showing current scale (e.g., "1/4\" = 1'-0\"") in status bar
- [x] Implement `PATCH /api/v1/sheets/:id/scale` endpoint
- [x] Scale persists across sessions (stored in `sheets` table)

### 2. Auto-Detect Scale
- [x] Parse PDF metadata for embedded scale information
- [x] Scan title block area for common scale notations (regex patterns):
  - "1/4\" = 1'-0\""
  - "Scale: 1:100"
  - "1\" = 10'"
  - etc.
- [x] If auto-detected, pre-fill the calibration dialog with the detected value
- [x] User confirms or overrides the detected value
- [x] Mark auto-detected scales with a visual indicator ("Auto-detected" badge)

### 3. Per-Sheet Scale Support
- [x] Each sheet stores its own scale independently
- [x] Scale indicator updates when switching sheets
- [x] Sheets without calibration show a "Not calibrated" warning
- [x] Prompt user to calibrate when they first try to use a measurement tool on an uncalibrated sheet

### 4. Text Search
- [x] Build text search index from extracted PDF text (processed in Sprint 04)
- [x] Create search UI: search input in the top bar or as a panel (`Ctrl+F`)
- [x] Search across all sheets, results grouped by sheet
- [x] Highlight matching text on the current sheet
- [x] Navigate between matches (next/previous buttons or Enter/Shift+Enter)
- [x] Show match count: "3 of 17 matches"
- [x] Clicking a result from another sheet switches to that sheet and zooms to the match

### 5. Toolbar Foundation
- [x] Create the takeoff toolbar in the top bar (center section)
- [x] Tool buttons: Select (V), Linear (L), Area (A), Count (C), Scale (S)
- [x] Active tool highlighted with accent background
- [x] Tools are non-functional in this sprint (just UI, measurement logic comes in Sprint 08-09)
- [x] Keyboard shortcuts for tool switching

---

## Acceptance Criteria

- [x] User can calibrate scale by drawing a known distance and entering the real-world value
- [x] Scale auto-detects from PDF metadata or title block notation when available
- [x] Each sheet has its own independent scale
- [x] Uncalibrated sheets show a warning when measurement tools are selected
- [x] Text search finds text across all sheets and highlights matches on the plan
- [x] User can navigate between search results (next/previous)
- [x] Searching across sheets switches to the correct sheet and zooms to the match
- [x] Toolbar shows all takeoff tools with keyboard shortcut support

---

## Key References

- [Plan Viewer Feature](../features/core/plan-viewer.md) -- scale calibration, text search
- [Screen Layouts - Plan Viewer Toolbar](../docs/design/screen-layouts.md)

## Implementation notes

- Scale is stored as **real-world units per PDF point** (`scale_value` + `scale_unit`), independent of zoom.
- `scale_source` column: `auto` (Celery heuristics) or `manual` (PATCH).
- Apply Supabase migration `supabase/migrations/20260416120000_sheets_scale_source.sql` for `scale_source`.
