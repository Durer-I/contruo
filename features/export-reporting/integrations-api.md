# Integrations & API

> **Category:** Export & Reporting
> **Priority:** P2 - Future
> **Status:** Deferred (to be brainstormed closer to build)

## Overview

Export data to accounting, ERP, and other construction software including QuickBooks, Sage, Procore, and more. Provides a REST API for programmatic access and webhook support for event-driven integrations. Enables Contruo to fit into existing construction technology workflows.

This feature is deferred for future planning. The full deep-dive -- including target integration priorities, API design, authentication model, and webhook event catalog -- will be conducted closer to the build phase when user feedback from the MVP informs which integrations are most in-demand.

## Key Concepts (To Be Expanded)

- **REST API**: programmatic access to projects, takeoffs, quantities, and conditions
- **Webhooks**: event-driven notifications when takeoff data changes
- **Direct integrations**: pre-built connectors for popular construction and accounting software
- **Excel/CSV import-export**: universal data exchange format (basic version available at MVP via PDF/Excel Export)

## Competitive Landscape

| Competitor | How They Handle It |
|------------|--------------------|
| PlanSwift | Exports to Excel/CSV. Plugin ecosystem for third-party integrations. No REST API. |
| Bluebeam | Exports markups to CSV/XML. Some third-party integrations via partners. No public API. |
| On-Screen Takeoff | Integrates with QuickBid (same vendor) for estimating. Excel export. Limited third-party integrations. |
| Togal.AI | Basic export capabilities. Limited integrations. Focused on the takeoff step, not the downstream workflow. |

## Notes

- The REST API is architecturally significant -- designing the internal API with future public exposure in mind from day one will save major refactoring later. Even though the public API ships in P2, the internal API patterns should be clean and consistent.
- Integration priorities should be driven by user research and early customer feedback. Procore, Sage, and QuickBooks are the most commonly requested in the construction tech space, but the actual priority depends on Contruo's customer base.
