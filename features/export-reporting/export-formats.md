# PDF/Excel Export

> **Category:** Export & Reporting
> **Priority:** P0 - MVP
> **Status:** Deep-Dive Complete

## Overview

Export takeoff quantities from Contruo as PDF or Excel files. At MVP, the export covers the **quantities table** (the same data shown in the quantities panel) for the **full project**. The output mirrors the grouped tree view layout with condition groupings and subtotals per condition and per sheet. No company branding at MVP -- exports use clean Contruo-formatted styling. Branding and customization come with the Custom Report Builder (P2).

## User Stories

- As an estimator, I want to export my takeoff quantities as an Excel file so that I can share the data with my team, client, or GC in a format they can work with.
- As an estimator, I want to export my takeoff quantities as a PDF so that I can include it in a bid proposal or print it for a meeting.
- As an estimator, I want the exported data to be grouped by condition with subtotals so that it matches how I organized my takeoff and is easy to read.
- As a project manager, I want to export the full project quantities in one click so that I can get a complete snapshot without manually selecting pieces.

## Key Requirements

### Export Formats
- **Excel (.xlsx)**: structured workbook with grouped rows and subtotals
- **PDF**: formatted table matching the Excel layout, paginated for print

### Export Content (MVP)
- Quantities table only -- the same data shown in the quantities panel
- No annotated plan snapshots at MVP
- No assembly item breakdowns in the export at MVP (quantities panel shows these, but export focuses on the primary measurement quantities)

### Export Scope
- Full project export -- all conditions, all sheets, all measurements
- No subset selection at MVP (no picking specific conditions or sheets to include/exclude)

### Excel Output Format
- Grouped by condition with subtotals, matching the quantities panel tree view:

```
Interior Wall - 8' Drywall                          Total: 1,250 LF
    Sheet A1.01 - First Floor           Subtotal:     500 LF
        Measurement 1                                 320 LF
        Measurement 2                                 180 LF
    Sheet A1.02 - Second Floor          Subtotal:     750 LF
        Measurement 3                                 410 LF
        Measurement 4                                 340 LF

Exterior Wall - Brick Veneer                         Total:   890 LF
    Sheet A1.01 - First Floor           Subtotal:     520 LF
        ...
```

- Columns: Name/Label, Quantity, Unit
- Condition rows bolded with totals
- Sheet rows indented with subtotals
- Measurement rows indented further with individual values
- Excel grouping/outline feature used so users can collapse/expand sections natively in Excel
- Grand total row at the bottom summing all conditions

### PDF Output Format
- Same layout as Excel but formatted for print/screen viewing
- Clean Contruo header with project name, date, and export timestamp
- Page numbers in footer
- Automatic pagination with condition groups kept together (avoid splitting a condition across pages when possible)
- Landscape or portrait orientation based on content width

### No Branding (MVP)
- Exports use Contruo's default clean styling
- No company logo, no custom headers/footers, no custom colors
- Project name and metadata shown in a simple header block
- Company branding capabilities deferred to the Custom Report Builder (P2)

### Export Trigger
- "Export" button accessible from the project toolbar or quantities panel
- Simple dialog: choose format (PDF or Excel) -> download starts
- Export generates server-side and delivers as a file download

## Nice-to-Have

- **Selective export**: choose which conditions, sheets, or trades to include
- **Annotated plan snapshots**: include plan images with colored measurements alongside the quantities table
- **Assembly item breakdown**: include derived assembly items (drywall sheets, studs, etc.) in the export
- **CSV export**: lightweight plain-text export for data pipelines
- **Scheduled exports**: auto-generate and email an export at set intervals
- **Export history**: keep a log of past exports for re-download
- **Print directly**: print the quantities table from within the app without downloading a file
- **Summary vs. detail toggle**: export a summary (condition totals only) or full detail (every measurement)
- **Multiple projects in one export**: combine quantities from related projects

## Competitive Landscape

| Competitor | How They Handle It |
|------------|--------------------|
| PlanSwift | Export to Excel with customizable column layouts. Print reports with branding. Multiple report templates. Can export annotated plan images. Desktop-only with local file save. |
| Bluebeam | Export markups summary to CSV/XML. PDF-native so the plan itself is the output. Markup lists can be exported but not structured as takeoff reports. |
| On-Screen Takeoff | Export to Excel and PDF. Grouped by condition with subtotals. Customizable report layouts. Can include plan page images. Desktop-only print dialog. |
| Togal.AI | Export AI-generated takeoff results to Excel/PDF. Simpler layout focused on area/linear quantities. Limited customization. |

## Open Questions

- [ ] Should the export include the measurement's override indicator (showing which values were manually adjusted)?
- [ ] What metadata should the PDF header include? (Project name, address, date, estimator name, export date?)
- [ ] Should Excel exports use named ranges or structured tables for easier downstream processing?
- [ ] How should very large projects (1000+ measurements) be handled in PDF export? (Table of contents? Condition-per-page?)

## Technical Considerations

- **Excel generation**: use a server-side library like ExcelJS (Node.js), openpyxl (Python), or similar. Excel grouping/outline feature requires specific API calls to set group levels on rows.
- **PDF generation**: use a library like Puppeteer (render HTML to PDF), PDFKit, or a reporting framework like JasperReports. HTML-to-PDF via Puppeteer is the fastest to develop and gives the most styling control.
- **Server-side generation**: exports should be generated on the server, not the client. Large projects would be too slow to process in the browser. The server renders the file and returns it as a download.
- **Async generation for large projects**: if export takes more than a few seconds, use an async job queue. Show a progress indicator and deliver the file when ready (or email a download link).
- The export data source is the same query that powers the quantities panel -- reuse the same aggregation logic to ensure the export always matches what the user sees on screen.
- File downloads need proper Content-Disposition headers and MIME types for browser download handling.

## Notes

- The MVP export is intentionally minimal: quantities table, full project, no branding. This covers the most critical use case -- "I need to get my numbers into a spreadsheet or a printable document to share with someone." Everything else is polish.
- The grouped Excel layout with native Excel grouping/outline is a power feature that estimators will appreciate. They can collapse/expand sections in Excel just like in the quantities panel, and the subtotals are always visible.
- No branding at MVP is the right call. Branding (logos, custom headers) is important for client-facing proposals but adds significant complexity (file upload, positioning, template management). The Custom Report Builder (P2) is the right home for this.
