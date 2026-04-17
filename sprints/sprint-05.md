# Sprint 05: Plan Viewer Core

> **Phase:** 2 - Plan Viewing
> **Duration:** 2 weeks
> **Status:** Complete
> **Depends On:** Sprint 04

## Sprint Goal

Build the core plan viewer — a high-performance, zoomable/pannable canvas that renders vector PDFs. At the end of this sprint, users can view their uploaded plans with smooth navigation, switch between sheets via the sheet index, and see the three-panel workspace layout.

---

## Tasks

### 1. Plan Viewer Canvas
- [x] Evaluate and integrate PDF rendering library — **pdf.js** (`pdfjs-dist` v5) with worker from unpkg (version-pinned)
- [x] Render vector PDF pages on HTML canvas (device pixel ratio for sharpness)
- [x] High-fidelity vector rendering via pdf.js viewport
- [x] Large sheets: re-render on zoom; pan uses CSS transform (no full re-render)

### 2. Zoom & Pan
- [x] Scroll wheel zoom (focal point preserved)
- [x] Pinch-to-zoom / trackpad: **Ctrl+wheel** (browser standard)
- [x] Zoom controls UI (zoom in, out, fit width, fit page)
- [x] Pan: **middle-click drag** or **Space + left-drag**
- [x] Zoom level indicator (status bar + `%` relative to fit-width baseline)
- [x] Min/max zoom via zoom multiplier bounds

### 3. Sheet Index Panel
- [x] Left panel (~18% default) with thumbnails and names
- [x] Click thumbnail to switch sheets (accent border on active)
- [x] Collapsible panels via `react-resizable-panels` (`collapsible` prop); drag-to-minimum collapses
- [x] Remember zoom/pan per sheet — `localStorage` key `contruo:sheetViewport:v1:{projectId}:{sheetId}`

### 4. Three-Panel Layout
- [x] Horizontal split: sheet index | viewer | quantities placeholder
- [x] Resizable dividers (`Group` / `Panel` / `Separator`)
- [x] Quantities placeholder copy (Sprint 11)
- [x] Persist panel sizes — `useDefaultLayout` + `localStorage`

### 5. Viewport Controls
- [x] Fit-to-page / fit-to-width (toolbar + imperative canvas API)
- [ ] Minimap — **deferred** (optional in spec)
- [x] Keyboard: `+` / `-` zoom, `[` / `]` previous/next sheet

### 6. Status Bar
- [x] Bottom bar (28px / `h-7`) in viewer column: sheet name, zoom %, hint line

---

## Acceptance Criteria

- [x] PDF plan renders with vector fidelity via pdf.js at varying zoom levels
- [x] Zoom in/out (wheel + buttons)
- [x] Pan (middle-click, Space+drag)
- [x] Sheet index lists sheets with thumbnails and names; click switches page
- [x] Three-panel layout with resizable panels and persisted layout
- [x] Panels support collapse via library behavior
- [x] Keyboard shortcuts for zoom and sheet navigation
- [x] Performance: pan avoids full PDF re-render; zoom re-renders one page

---

## Delivered Artifacts

**Backend**
- `GET /api/v1/plans/{plan_id}/document-url` — returns `{ url, expires_in }` (Supabase signed URL for raw PDF)
- `plan_service.get_plan_document_signed_url`, schema `PlanDocumentUrlResponse`
- Test: `test_get_plan_document_url_returns_signed_url`

**Frontend**
- `lib/pdf-worker.ts` — pdf.js worker bootstrap
- `components/plan-viewer/sheet-viewport-storage.ts` — per-sheet viewport persistence
- `components/plan-viewer/plan-pdf-canvas.tsx` — canvas, wheel zoom, pan, fit, ref API
- `components/plan-viewer/plan-viewer-workspace.tsx` — `Group`/`Panel` layout, sheet list, toolbar, status, document URL fetch
- `app/(app)/project/[id]/page.tsx` — integrates workspace when sheets exist; upload strip below
- `types/project.ts` — `PlanDocumentUrlResponse`
- `components/layout/app-shell.tsx` — main uses flex + `overflow-hidden` so viewer fills height; scroll wrappers on other pages

---

## Key References

- [Plan Viewer Feature](../features/core/plan-viewer.md)
- [Screen Layouts - Plan Viewer](../docs/design/screen-layouts.md)
- [Design System](../docs/design/design-system.md)
