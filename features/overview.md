# Contruo - Feature Overview

Contruo is an online SaaS platform for construction estimators to create, edit, and manage takeoffs efficiently. It enables real-time collaboration across teams and leverages AI to automate the takeoff process, allowing estimators to focus on review and refinement rather than manual measurement.

**Target Market:** General Contractors, Subcontractors / Specialty Trades, Dedicated Estimating Firms & Consultants

**Key Competitors:** PlanSwift, Bluebeam Revu, On-Screen Takeoff (OST), Togal.AI

---

## Feature Categories

### 1. Core Takeoff

The foundational measurement and quantity tools that power every takeoff.

| Feature | Description | Priority | Status |
|---------|-------------|----------|--------|
| [Plan Viewer](core/plan-viewer.md) | Vector PDF rendering, zoom/pan, smart sheet index, scale calibration, text search | P0 - MVP | Deep-Dive Complete |
| [Linear Takeoff](core/linear-takeoff.md) | Click-to-click + freehand + snap-to-geometry, arcs, running totals, vertex editing, deductions | P0 - MVP | Deep-Dive Complete |
| [Area Takeoff](core/area-takeoff.md) | Polygon/rect/circle + snap-to-room, cutouts (boolean + inner boundary), auto perimeter | P0 - MVP | Deep-Dive Complete |
| [Count Takeoff](core/count-takeoff.md) | Rapid-click markers, colored dots, per-sheet + project-wide totals | P0 - MVP | Deep-Dive Complete |
| [Volume Takeoff](core/volume-takeoff.md) | Area x depth via formula engine (leverages existing tools) | P1 - Post-Launch | Light Brainstorm |
| [Conditions & Assemblies](core/conditions-and-assemblies.md) | Conditions with styling + custom properties, assembly items with formulas, org template library | P0 - MVP | Deep-Dive Complete |
| [Quantity Management](core/quantity-management.md) | Grouped tree view, condition + sheet subtotals, bidirectional plan linking, manual overrides | P0 - MVP | Deep-Dive Complete |

### 2. Project Management

Tools for organizing projects, plans, and bids. **On backburner -- not yet brainstormed.**

| Feature | Description | Priority | Status |
|---------|-------------|----------|--------|
| [Project Dashboard](project-management/project-dashboard.md) | Overview of all projects, statuses, deadlines, team assignments | P0 - MVP | Stub |
| [Plan Management](project-management/plan-management.md) | Upload, version, and organize plan sets; plan revisions and comparisons | P0 - MVP | Stub |
| [Bid Management](project-management/bid-management.md) | Track bids, deadlines, bid/no-bid decisions, proposal generation | P1 - Post-Launch | Stub |

### 3. Collaboration

Real-time multi-user features that enable teams to work together on takeoffs.

| Feature | Description | Priority | Status |
|---------|-------------|----------|--------|
| [Real-Time Multi-User Editing](collaboration/real-time-editing.md) | Figma-style same-sheet editing, live cursors, lock-on-select, 2-5 users | P0 - MVP | Deep-Dive Complete |
| [Roles & Permissions](collaboration/roles-and-permissions.md) | Fixed roles (Owner/Admin/Estimator/Viewer), org-level, guest accounts | P0 - MVP | Deep-Dive Complete |
| [Comments & Markup](collaboration/comments-and-markup.md) | Comments on measurements, @mentions, threaded conversations, in-app + email notifications | P1 - Post-Launch | Light Brainstorm |
| [Activity Log & Version History](collaboration/activity-log.md) | View-only audit trail, event logging from day one, future rollback ready | P1 - Post-Launch | Light Brainstorm |

### 4. Cost & Estimation

Pricing, cost management, and estimate generation tools. **On backburner -- not yet brainstormed.**

| Feature | Description | Priority | Status |
|---------|-------------|----------|--------|
| [Cost Database](cost-estimation/cost-database.md) | Manage material, labor, and equipment cost items with unit costs | P1 - Post-Launch | Stub |
| [Estimate Builder](cost-estimation/estimate-builder.md) | Build detailed estimates from takeoff quantities with cost assignments | P1 - Post-Launch | Stub |
| [Pricing Templates](cost-estimation/pricing-templates.md) | Reusable pricing templates for common assemblies and trades | P1 - Post-Launch | Stub |
| [Waste & Markup Factors](cost-estimation/waste-and-markup.md) | Apply waste percentages, overhead, profit margins, contingencies | P1 - Post-Launch | Stub |

### 5. Export & Reporting

Getting data out of Contruo and into other systems.

| Feature | Description | Priority | Status |
|---------|-------------|----------|--------|
| [PDF/Excel Export](export-reporting/export-formats.md) | Full project quantities export, grouped by condition with subtotals, Excel outline grouping | P0 - MVP | Deep-Dive Complete |
| [Custom Report Builder](export-reporting/custom-reports.md) | Branded templates with configurable sections and layouts | P2 - Future | Light Brainstorm |
| [Integrations & API](export-reporting/integrations-api.md) | REST API, webhooks, connectors to accounting/ERP software | P2 - Future | Deferred |

### 6. AI Features

AI-powered automation to streamline the takeoff and estimation process. **On backburner -- not yet brainstormed.**

| Feature | Description | Priority | Status |
|---------|-------------|----------|--------|
| [AI Auto-Takeoff](ai/ai-auto-takeoff.md) | Automatically detect and measure elements from plans using computer vision | P1 - Post-Launch | Stub |
| [AI Element Recognition](ai/ai-element-recognition.md) | Identify doors, windows, walls, fixtures, MEP elements from plan sheets | P1 - Post-Launch | Stub |
| [AI Quantity Suggestions](ai/ai-quantity-suggestions.md) | Suggest quantities and assemblies based on plan analysis | P2 - Future | Stub |
| [AI Cost Estimation](ai/ai-cost-estimation.md) | Auto-suggest pricing based on historical data and market rates | P2 - Future | Stub |
| [AI Plan Comparison](ai/ai-plan-comparison.md) | Automatically detect differences between plan revisions | P2 - Future | Stub |

### 7. Platform & Infrastructure

Authentication, billing, and organizational management.

| Feature | Description | Priority | Status |
|---------|-------------|----------|--------|
| [Authentication & Onboarding](platform/auth-and-onboarding.md) | Email/password auth, org-required signup, welcome modal, invitations, guest accounts | P0 - MVP | Deep-Dive Complete |
| [Subscription & Billing](platform/subscription-and-billing.md) | Single plan, per-seat annual billing, DodoPayments, prorated seat management | P0 - MVP | Deep-Dive Complete |
| [Organization Management](platform/organization-management.md) | Flat org structure, minimal settings (name, logo, units), multi-tenant data isolation | P0 - MVP | Deep-Dive Complete |

---

## Priority Legend

| Priority | Meaning | Timeline |
|----------|---------|----------|
| **P0 - MVP** | Must-have for initial launch | Sprints 01-16 (~32 weeks) |
| **P1 - Post-Launch** | High-value features for immediate post-launch iteration | Post-launch |
| **P2 - Future** | Strategic features for long-term roadmap | Future |

---

## Planning Status Summary

| Status | Count | Meaning |
|--------|-------|---------|
| **Deep-Dive Complete** | 17 | Fully brainstormed with user stories, requirements, competitive analysis, technical considerations |
| **Light Brainstorm** | 4 | Concept defined, basic requirements, to be expanded closer to build |
| **Stub** | 5 | Template created, not yet brainstormed (backburner categories) |
| **Deferred** | 2 | Intentionally postponed, will brainstorm when closer to build |

## Additional Documentation

| Document | Purpose |
|----------|---------|
| [Design System](../docs/design/design-system.md) | Colors, typography, spacing, shadcn customization, dark theme |
| [Screen Layouts](../docs/design/screen-layouts.md) | 7 key screen wireframes, UX flows, keyboard shortcuts |
| [Backend Architecture](../docs/architecture/backend.md) | FastAPI structure, DB schema, API endpoints, integrations |
| [Frontend Architecture](../docs/architecture/frontend.md) | Next.js structure, routing, state management, canvas rendering |
| [Testing Strategy](../docs/testing-strategy.md) | Test stack, coverage targets, CI pipeline, per-sprint testing plan |
| [Sprint Roadmap](../sprints/roadmap.md) | 16 sprints across 6 phases, dependency graph, feature mapping |
