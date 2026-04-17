# Area Takeoff

> **Category:** Core Takeoff
> **Priority:** P0 - MVP
> **Status:** Deep-Dive Complete

## Overview

Measure area elements on construction plans -- flooring, roofing, painting surfaces, concrete slabs, ceiling areas, insulation, waterproofing, and any element measured in square footage or meters. Users define boundaries using polygon, rectangle, circle/ellipse tools, or snap-to-room auto-detection from PDF vectors. Supports interior cutouts (voids), automatic perimeter calculation, and condition-styled rendering. Area measurements feed into the formula engine for derived quantities.

## User Stories

- As an estimator, I want to draw a polygon around a room to calculate its floor area so that I can determine flooring material quantities.
- As an estimator, I want a quick rectangle tool for regular-shaped rooms so that I can measure simple spaces faster.
- As an estimator, I want the system to auto-detect enclosed room boundaries from the PDF vector lines so that I can measure room areas with a single click.
- As an estimator, I want to cut out interior voids (columns, shafts, stairwells) from an area measurement so that my net area is accurate.
- As an estimator, I want the perimeter to be automatically calculated whenever I measure an area so that I can use it for baseboard, edge trim, and other perimeter-based quantities.
- As an estimator, I want to edit the boundary vertices of a completed area measurement so that I can adjust mistakes without redrawing.
- As an estimator, I want each area measurement styled with the condition's color and fill pattern so that I can visually distinguish different surface types on the plan.
- As an estimator, I want to define formulas that use the area and perimeter as inputs so that I can auto-calculate derived quantities (e.g., area x material coverage rate).

## Key Requirements

### Shape Tools
- **Polygon**: Click to place vertices defining an irregular boundary, double-click or Enter to close
- **Rectangle**: Click-drag to define a rectangular area (with optional dimension input for exact sizing)
- **Circle / Ellipse**: Click-drag to define circular or elliptical areas
- **Snap-to-room**: Click inside an enclosed space and the system auto-detects the room boundary from PDF vector geometry

### Cutouts / Voids (Both Methods Supported)
- **Boolean subtraction**: Draw a separate shape overlapping the area, then subtract it to create a void. The subtracted shape can be reused across multiple areas.
- **Inner boundary**: While defining a polygon area, switch to "hole mode" to draw interior boundaries that are part of the same area definition. The hole is drawn as a polygon within the outer boundary.
- Both methods produce the same result: net area = gross area minus void areas
- Voids are visually represented (e.g., hatched or transparent within the filled area)
- Void areas and net/gross totals are shown in the quantities panel

### Automatic Perimeter Calculation
- Every area measurement auto-calculates its outer perimeter
- If cutouts exist, both outer perimeter and total perimeter (including cutout edges) are available
- Perimeter is available as a formula variable for derived quantity calculations
- Perimeter values appear in the quantities panel alongside the area

### Measurement Display
- Areas rendered with condition-defined styling: fill color, fill opacity, border color, fill pattern (solid, hatch, crosshatch)
- Area measurement label shown inside the shape (e.g., "1,250 SF") that scales with zoom
- Hover/select to see full details: gross area, void area, net area, perimeter, derived quantities

### Vertex Editing (Post-Draw)
- Click a completed area to enter edit mode
- Drag vertices to reshape the boundary
- Add new midpoints by clicking on an edge
- Delete vertices by selecting and pressing Delete
- Edit cutout boundaries independently
- All edits recalculate area, perimeter, and derived quantities in real-time

### Formula-Based Derived Quantities
- Uses the same formula engine as Linear Takeoff
- Available variables: area, perimeter, and custom condition properties
- Common examples: area x coverage rate = material quantity, perimeter x baseboard height = trim area

## Nice-to-Have

- Slope/pitch adjustment factor per condition (e.g., 6:12 roof pitch multiplier) -- planned for post-MVP
- Auto-split: draw one large area and split it into sub-areas by room boundaries
- Area measurement from room schedule cross-reference
- Multi-floor area duplication (measure once, apply to multiple identical floors)
- AI-assisted boundary detection for rooms that aren't fully enclosed in the vectors
- Area decomposition view showing how the total was calculated (gross - voids = net)

## Competitive Landscape

| Competitor | How They Handle It |
|------------|--------------------|
| PlanSwift | Polygon and rectangle tools for area measurement. Supports cutouts via separate deduction areas. Condition-styled fills. Running area total. Vertex editing available. No snap-to-room. Desktop-only. |
| Bluebeam | Area measurement tool as part of markup. Polygon-based. Supports cutouts. Not connected to a takeoff database -- measurements are standalone annotations. Has calibration but not takeoff-centric. |
| On-Screen Takeoff | Polygon and rectangle area tools. Condition-based styling with fill patterns. Cutouts supported. Perimeter auto-calculated. Vertex editing limited. Desktop-only. No snap-to-room. |
| Togal.AI | AI auto-detects room boundaries and calculates areas automatically. Minimal manual drawing tools. Strength is in automated detection, weakness is in manual adjustment when AI is wrong. |

## Open Questions

- [ ] How should snap-to-room handle partially enclosed rooms (e.g., open floor plans with no wall on one side)?
- [ ] Should the rectangle tool support rotation for rooms that aren't aligned to the page axis?
- [ ] How do we handle overlapping area measurements from different conditions (e.g., floor area and ceiling area on the same room)?
- [ ] What's the maximum polygon complexity (vertex count) before performance degrades?
- [ ] Should cutout voids be shareable/reusable across multiple area measurements?

## Technical Considerations

- Snap-to-room requires flood-fill algorithm on the PDF vector geometry to detect enclosed boundaries -- computationally expensive but very valuable UX
- Boolean polygon operations (union, subtraction, intersection) need a robust computational geometry library (e.g., Clipper, Turf.js, or similar)
- Area and perimeter calculation for complex polygons with holes uses the shoelace formula with hole subtraction
- Real-time vertex editing with area recalculation needs efficient incremental computation
- Rendering semi-transparent filled polygons with patterns requires careful layering to maintain plan readability
- Collaboration sync needs to handle polygon vertex arrays and cutout references as atomic operations

## Notes

- Snap-to-room auto-detection is a major differentiator and one of the biggest time-savers for estimators. Competitors like PlanSwift and OST don't offer it. Togal.AI does it via AI, but Contruo's approach using actual vector geometry is more reliable and deterministic.
- The combination of auto-perimeter + formula engine means a single area measurement can produce floor material quantities, baseboard quantities, ceiling quantities, and paint quantities simultaneously -- huge productivity multiplier.
- The two cutout methods (boolean subtraction and inner boundary) cover different workflow preferences and both are needed for a professional-grade tool.
