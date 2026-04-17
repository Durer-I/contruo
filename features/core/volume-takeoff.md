# Volume Takeoff

> **Category:** Core Takeoff
> **Priority:** P1 - Post-Launch
> **Status:** Light Brainstorm (to be expanded closer to build)

## Overview

Calculate volumes for construction elements such as excavation, fill, concrete pours, and earthwork. The initial approach leverages the existing Area Takeoff tool combined with the formula engine -- users measure an area and define a depth/height variable on the condition to compute volume (area x depth). A dedicated volume tool with more advanced 3D capabilities (varying depths, grade differentials) may follow for complex earthwork scenarios.

## User Stories

- As an estimator, I want to measure an area and enter a depth so that I can calculate the volume of a concrete slab, excavation, or fill.
- As an estimator, I want to define a depth/height variable on a condition so that volume is auto-calculated from every area measurement using that condition.
- As a site work estimator, I want to calculate cut/fill volumes from grade differentials so that I can estimate earthwork quantities.

## Key Requirements

### Phase 1: Formula-Based Volume (Leverages Existing Tools)
- Use Area Takeoff to define the footprint boundary
- Define a "depth" or "height" property on the condition
- Formula engine computes: volume = area x depth
- Volume appears as a derived quantity in the quantities panel
- Supports different depths per condition (e.g., 4" slab vs. 6" slab)

### Phase 2: Dedicated Volume Tool (Future)
- Dedicated UI for defining varying depths across an area (e.g., excavation that goes from 2' to 8' deep)
- Grade-to-grade calculations for earthwork (existing grade vs. proposed grade)
- Cross-section based volume calculation
- Import survey/grading data

## Nice-to-Have

- 3D visualization preview of volumes
- Cut/fill balance calculations
- Integration with civil engineering grade data
- Volume decomposition view (showing how depth varies across the area)

## Competitive Landscape

| Competitor | How They Handle It |
|------------|--------------------|
| PlanSwift | Volume calculated as area x depth via condition properties. No dedicated 3D volume tool. |
| Bluebeam | Volume measurement available as a markup tool. Basic area x depth. Not connected to takeoff database. |
| On-Screen Takeoff | Supports volume via area conditions with depth property. Similar formula-based approach. |
| Togal.AI | Limited volume support. Focused on 2D area/linear detection. |

## Open Questions

- [ ] Is the formula-based approach sufficient for 90%+ of volume use cases, or is a dedicated tool needed sooner?
- [ ] How common are complex earthwork/grading volume needs among our target users?
- [ ] Should we integrate with any civil/survey tools for grade data import?

## Technical Considerations

- Phase 1 requires no new engineering -- it's purely a formula setup on Area Takeoff conditions
- Phase 2 (varying depth volumes) would need a depth grid or TIN (triangulated irregular network) model
- This feature's Phase 1 is a good example of the formula engine's power -- worth highlighting in marketing

## Notes

- The "area x depth" approach via the formula engine covers the vast majority of volume needs (slabs, footings, trenches, simple excavation). This makes Volume Takeoff essentially free to ship once Area Takeoff and the formula engine are complete.
- Complex earthwork volume calculations are a niche need primarily for site work contractors. A dedicated tool can be evaluated based on user demand post-launch.
