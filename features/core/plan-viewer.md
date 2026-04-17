# Plan Viewer

> **Category:** Core Takeoff
> **Priority:** P0 - MVP
> **Status:** Deep-Dive Complete

## Overview

The Plan Viewer is the foundational canvas of Contruo -- every takeoff measurement, annotation, and collaboration interaction happens on top of it. It renders vector PDF construction plans in a high-performance, zoomable/pannable viewport with smart sheet indexing, scale calibration, and text search. The viewer is paired with a quantities panel in a vertical split layout (plan left, quantities right).

## User Stories

- As an estimator, I want to upload a multi-page PDF plan set so that I can begin taking off quantities from the construction drawings.
- As an estimator, I want to zoom, pan, and navigate smoothly across large plan sheets so that I can inspect fine details and work efficiently.
- As an estimator, I want to calibrate the scale of a plan so that all my measurements are accurate to real-world dimensions.
- As an estimator, I want the system to auto-detect the scale from PDF metadata or title block notation so that I don't have to manually calibrate every sheet.
- As an estimator, I want to see a smart sheet index that auto-detects sheet names/numbers (e.g., A1.01, M2.03) alongside thumbnails so that I can quickly jump between sheets.
- As an estimator, I want to search for text within the plan (room names, labels, dimensions, notes) so that I can quickly locate specific areas.
- As a project manager, I want to see which sheets have takeoff work completed and which are untouched so that I can track progress.

## Key Requirements

### File Format Support
- Vector PDF support (the primary and only format at MVP)
- Multi-page PDF handling with automatic page detection
- High-fidelity rendering that preserves line weights, colors, text, and vector detail

### Navigation & Viewport
- Smooth zoom (scroll wheel, pinch-to-zoom, zoom controls) with no lag even on large sheets
- Pan/scroll with mouse drag or trackpad gestures
- Fit-to-page, fit-to-width, and zoom-to-selection controls
- Minimap or overview indicator showing current viewport position on the full sheet
- Keyboard shortcuts for navigation (zoom in/out, fit, pan)

### Sheet Management
- Smart sheet index sidebar that parses sheet names/numbers from the PDF (e.g., "A1.01 - First Floor Plan")
- Thumbnail previews for all sheets
- Quick switch between sheets without losing zoom/pan state on previous sheets
- Remember last viewed position per sheet

### Scale Calibration
- Manual calibration: user draws a line between two known points and enters the real-world distance
- Auto-detect from PDF metadata (embedded scale information)
- Auto-detect from title block scale notation (e.g., "1/4\" = 1'-0\"")
- AI-assisted scale detection as a fallback
- Per-sheet scale support (different sheets can have different scales)
- Visual indicator showing current scale and unit system

### Text Search
- Full-text search across all text content in the vector PDF
- Highlight matching results on the plan with navigation between matches
- Search across all sheets with results grouped by sheet

### Layout
- Vertical split layout: Plan Viewer on the left, Quantities Panel on the right
- Resizable split divider so users can adjust the ratio
- Ability to collapse the quantities panel for full-screen plan viewing

## Nice-to-Have

- PDF layer toggle (show/hide individual layers for MEP plan overlays) -- planned for post-MVP
- Plan revision overlay/comparison (side-by-side or opacity slider) -- planned for post-MVP
- General annotations (text, arrows, highlights) beyond takeoff measurements -- planned for post-MVP
- Dark mode / inverted plan colors for reducing eye strain
- Bookmarks for saving specific locations/zoom levels on a sheet
- Measurement snapping to vector geometry in the PDF

## Competitive Landscape

| Competitor | How They Handle It |
|------------|--------------------|
| PlanSwift | Desktop app with proprietary plan viewer. Supports PDF, images, DWG. Has digitizer tablet support. Page tabs across the top. Manual scale calibration only. |
| Bluebeam | Industry-leading PDF viewer with extensive markup tools. Layer support, measurement tools, overlay comparison. Very feature-rich but primarily a PDF tool, not a takeoff-first product. |
| On-Screen Takeoff | Desktop app with plan viewer supporting PDF and images. Page list sidebar with thumbnails. Manual scale calibration with a two-point method. Split view with conditions panel. |
| Togal.AI | Web-based viewer focused on AI takeoff. Simpler viewer UI since the emphasis is on automated measurement. Upload PDF, AI processes it. Less manual navigation needed. |

## Open Questions

- [ ] What PDF rendering engine/library should we use for the web? (pdf.js, PSPDFKit, Apryse, or custom?)
- [ ] How do we handle extremely large PDFs (500+ MB, 200+ pages) without degrading performance?
- [ ] Should we pre-process/rasterize PDFs server-side at multiple zoom levels for faster rendering, or render vectors client-side?
- [ ] How accurate can AI-based scale detection be across different title block formats?
- [ ] Should sheet name parsing be rule-based or AI-assisted for non-standard naming?

## Technical Considerations

- Vector PDF rendering in the browser is computationally expensive at high zoom levels -- may need a hybrid approach (vector at low zoom, rasterized tiles at high zoom)
- PDF.js is open-source but may lack performance for large construction plans; commercial SDKs (PSPDFKit, Apryse) offer better performance but add licensing cost
- Scale calibration state needs to persist per-sheet and sync across collaborators in real-time
- Text search requires extracting and indexing the PDF text layer, which can be done at upload time
- Smart sheet index parsing will need heuristics for common naming conventions (AIA standards, custom formats)
- The viewport state (zoom, pan, active sheet) is the foundation for collaboration cursor syncing later

## Notes

- The Plan Viewer is the single most performance-critical component in the entire product. If it feels sluggish, users will abandon the product immediately. Construction plans are large, detailed documents and estimators spend hours staring at them.
- Starting with vector PDFs only is a smart MVP scoping decision -- it covers the vast majority of plans shared digitally today. DWG/DXF and image support can follow.
- The vertical split layout (plan left, quantities right) mirrors the mental model of most estimators who are used to PlanSwift/OST layouts.
