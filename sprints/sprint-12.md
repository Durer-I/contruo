# Sprint 12: Export

> **Phase:** 4 - Data & Export
> **Duration:** 2 weeks
> **Status:** Complete (MVP)
> **Depends On:** Sprint 11

## Sprint Goal

Build the PDF and Excel export functionality. At the end of this sprint, users can export the full project quantities as an Excel workbook (with grouped rows and subtotals) or a formatted PDF, and download the file.

---

## Tasks

### 1. Export Dialog UI
- [x] Create export dialog (triggered from toolbar "Export" button or `Ctrl+E`)
- [x] Format selection: Excel (.xlsx) or PDF radio buttons
- [x] Scope display: "Full Project" with summary (X conditions, Y measurements, Z sheets)
- [x] Export button triggers server-side generation
- [x] Loading/progress indicator while generating
- [x] Auto-download on completion

### 2. Excel Export (Server-Side)
- [x] Create `export_service.py` with Excel generation logic
- [x] Use openpyxl (Python) library
- [x] Grouped layout matching the quantities panel tree view:
  - Condition rows: bold, with grand total
  - Sheet rows: indented, with subtotal
  - Measurement rows: indented further, with individual values
- [x] Columns: Name/Label, Quantity, Unit
- [x] Excel grouping/outline feature: row `outline_level` set for condition / sheet / measurement rows
- [x] Grand total row at the bottom (with mixed-unit caveat)
- [x] Header row: project name, export date
- [x] Column auto-width for readability

### 3. PDF Export (Server-Side)
- [x] PDF generation using reportlab
- [x] Same layout as Excel but formatted for print/screen viewing
- [x] Clean Contruo header: project name, date, export timestamp
- [x] Page numbers in footer (via canvas hook)
- [ ] Automatic pagination with condition groups kept together — partial (single flowing table; large conditions may split across pages)
- [x] Landscape orientation for wide table
- [x] Professional table styling (dark header, zebra rows)

### 4. Export API
- [x] Implement `POST /api/v1/projects/:id/export` endpoint
  - Accepts format parameter (xlsx or pdf)
  - Queues a Celery task for generation
  - Returns an export job ID (Celery task id)
- [x] Implement `GET /api/v1/exports/:id` status (signed download URL when ready) and `GET /api/v1/exports/:id/download` (302 to signed URL)
- [x] Store generated exports in Supabase Storage bucket `exports` (org-scoped paths). **24h auto-expire:** configure via Supabase Storage lifecycle / cron (not in app code).
- [x] Async generation with client polling for signed URL

### 5. Export Data Source
- [x] Same tree aggregation as quantities panel (conditions → sheets → measurements)
- [x] Override values in quantity column with measured value in parentheses when overridden
- [x] Assembly items NOT included in export at MVP

### 6. Event Logging
- [x] Log `export.generated` events with format, project_id, storage path, filename

---

## Acceptance Criteria

- [x] User can open the export dialog and choose Excel or PDF format
- [x] Excel export produces a .xlsx file with grouped rows, subtotals, and proper formatting
- [x] Excel outline levels for native collapse/expand (where supported)
- [x] PDF export produces a paginated document with headers, footers, and page numbers
- [x] Exported data matches the quantities panel tree (same grouping and values)
- [x] Overridden values are reflected in the export
- [x] File downloads automatically after generation (signed URL fetch → blob download)
- [x] Large exports handled asynchronously via Celery (no long HTTP hold on POST)

---

## Key References

- [PDF/Excel Export Feature](../features/export-reporting/export-formats.md)
- [Screen Layouts - Export Dialog](../docs/design/screen-layouts.md)
