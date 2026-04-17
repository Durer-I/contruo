# Custom Report Builder

> **Category:** Export & Reporting
> **Priority:** P2 - Future
> **Status:** Light Brainstorm (to be expanded closer to build)

## Overview

Build custom report templates with company branding, configurable sections, and flexible layouts. Allows organizations to create standardized report formats that match their internal processes and client expectations. This is the evolution of the basic PDF/Excel export -- moving from "export the data" to "create a professional, branded document."

## User Stories

- As an admin, I want to upload my company logo and set brand colors so that all exported reports carry our company identity.
- As an estimator, I want to choose from pre-built report templates so that I can generate a professional-looking proposal without designing it from scratch.
- As a project manager, I want to create a custom report layout that includes only the sections my client needs so that the deliverable is clean and focused.

## Key Requirements (High-Level Vision)

- Company branding: logo, company name, contact info, brand colors in headers/footers
- Configurable sections: choose which data blocks to include (summary, detail, plan images, assembly breakdown, notes)
- Section ordering and layout control
- Save templates at the organization level for reuse across projects
- Contruo-provided starter templates for common report formats

## Nice-to-Have

- Drag-and-drop template editor
- Custom cover page design
- Table of contents for large reports
- Conditional sections (e.g., only show assembly breakdown if assemblies exist)
- Multi-format output from the same template (PDF, Word, Excel)

## Competitive Landscape

| Competitor | How They Handle It |
|------------|--------------------|
| PlanSwift | Built-in report designer with customizable templates. Headers, footers, branding. Multiple pre-built templates. |
| Bluebeam | PDF-native -- users create their own report formats as Bluebeam documents. Not a structured report builder. |
| On-Screen Takeoff | Customizable report layouts with branding. Print preview and formatting options. |
| Togal.AI | Limited report customization. Basic export formatting. |

## Open Questions

- [ ] Should the report builder be a visual WYSIWYG editor or a template-with-placeholders system?
- [ ] How much layout control is needed? (Simple section ordering vs. full page layout design?)
- [ ] Should reports be generated client-side or server-side?

## Technical Considerations

- This feature builds on top of the PDF/Excel export infrastructure from the MVP
- Template storage and rendering engine need to be flexible enough for diverse layouts
- Consider using a templating language (Handlebars, Liquid) for the template engine

## Notes

- This feature is the bridge between "tool output" and "professional deliverable." Construction firms care deeply about how their proposals look to clients. A well-designed report builder can be a significant competitive advantage and a driver for higher-tier subscription plans.
- Defer to P2 is correct -- the basic export covers MVP needs, and the report builder is a large UX and engineering effort that benefits from having real user feedback on what report formats they actually need.
