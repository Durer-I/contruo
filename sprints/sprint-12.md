# Sprint 12: Export

> **Phase:** 4 - Data & Export
> **Duration:** 2 weeks
> **Status:** Not Started
> **Depends On:** Sprint 11

## Sprint Goal

Build the PDF and Excel export functionality. At the end of this sprint, users can export the full project quantities as an Excel workbook (with grouped rows and subtotals) or a formatted PDF, and download the file.

---

## Tasks

### 1. Export Dialog UI
- [ ] Create export dialog (triggered from toolbar "Export" button or `Ctrl+E`)
- [ ] Format selection: Excel (.xlsx) or PDF radio buttons
- [ ] Scope display: "Full Project" with summary (X conditions, Y measurements, Z sheets)
- [ ] Export button triggers server-side generation
- [ ] Loading/progress indicator while generating
- [ ] Auto-download on completion

### 2. Excel Export (Server-Side)
- [ ] Create `export_service.py` with Excel generation logic
- [ ] Use ExcelJS (if Node) or openpyxl (Python) library
- [ ] Grouped layout matching the quantities panel tree view:
  - Condition rows: bold, with grand total
  - Sheet rows: indented, with subtotal
  - Measurement rows: indented further, with individual values
- [ ] Columns: Name/Label, Quantity, Unit
- [ ] Excel grouping/outline feature: rows grouped so users can collapse/expand in Excel natively
- [ ] Grand total row at the bottom
- [ ] Header row: project name, export date
- [ ] Column auto-width for readability

### 3. PDF Export (Server-Side)
- [ ] PDF generation using a library (WeasyPrint, Puppeteer, or reportlab)
- [ ] Same layout as Excel but formatted for print/screen viewing
- [ ] Clean Contruo header: project name, date, export timestamp
- [ ] Page numbers in footer
- [ ] Automatic pagination with condition groups kept together (avoid splitting mid-condition)
- [ ] Landscape or portrait orientation based on content width
- [ ] Professional table styling matching Contruo's design aesthetic

### 4. Export API
- [ ] Implement `POST /api/v1/projects/:id/export` endpoint
  - Accepts format parameter (xlsx or pdf)
  - Queues a Celery task for generation
  - Returns an export job ID
- [ ] Implement `GET /api/v1/exports/:id/download` endpoint
  - Returns the generated file as a download
  - Proper Content-Disposition header and MIME type
- [ ] Store generated exports temporarily in Supabase Storage (auto-expire after 24 hours)
- [ ] Handle large exports asynchronously (progress polling)

### 5. Export Data Source
- [ ] Reuse the same aggregation query that powers the quantities panel
- [ ] Ensure export data exactly matches what the user sees on screen
- [ ] Include override values where applicable (with original measured value in parentheses)
- [ ] Assembly items NOT included in export at MVP (quantities panel primary values only)

### 6. Event Logging
- [ ] Log `export.generated` events with format, project_id, user_id, timestamp

---

## Acceptance Criteria

- [ ] User can open the export dialog and choose Excel or PDF format
- [ ] Excel export produces a .xlsx file with grouped rows, subtotals, and proper formatting
- [ ] Excel grouping/outline allows collapsing/expanding in Excel natively
- [ ] PDF export produces a paginated document with headers, footers, and page numbers
- [ ] Exported data matches the quantities panel exactly
- [ ] Overridden values are reflected in the export
- [ ] File downloads automatically after generation
- [ ] Large exports (500+ measurements) generate without timeout

---

## Key References

- [PDF/Excel Export Feature](../features/export-reporting/export-formats.md)
- [Screen Layouts - Export Dialog](../docs/design/screen-layouts.md)
