# Contruo Screen Layouts & UX Flows

> **Status:** In Progress
> **Reference:** [Design System](design-system.md)

---

## Application Shell

The overall app structure follows a **sidebar + main content** pattern, similar to Figma, Linear, and VS Code.

```
┌──────────────────────────────────────────────────────────┐
│  Top Bar (48px height)                                   │
│  [Logo] [Project Name ▼]  [Toolbar...]  [Avatars] [⚙]  │
├────────┬─────────────────────────────────────────────────┤
│        │                                                 │
│  Side  │           Main Content Area                     │
│  bar   │                                                 │
│ (240px)│  (varies by context: workspace, project,        │
│        │   plan viewer, settings, etc.)                  │
│        │                                                 │
│        │                                                 │
│        │                                                 │
│        │                                                 │
└────────┴─────────────────────────────────────────────────┘
```

### Top Bar (48px)
- **Left**: Contruo logo (icon only, ~24px) + current project name as a dropdown (switch projects)
- **Center**: Contextual toolbar (changes based on the active view -- takeoff tools when in plan viewer, nothing when in settings)
- **Right**: Online user avatars (collaboration presence), notification bell (future), user avatar dropdown (profile, settings, logout)
- Background: `--surface`, bottom border: `--border`

### Sidebar (240px, collapsible to 48px)
- **Navigation items**: Dashboard, Projects, Templates (condition library), Settings, Billing
- When inside a project: switches to project-scoped navigation (Sheets, Conditions, Quantities, Export)
- Collapsible to icon-only (48px) mode via a toggle at the bottom
- Collapse state persisted in local storage
- Background: `--surface`, right border: `--border`

---

## Screen 1: Dashboard / Home

The first screen after login. Shows all projects in the organization.

```
┌──────────────────────────────────────────────────────────┐
│  Top Bar                                                 │
├────────┬─────────────────────────────────────────────────┤
│        │                                                 │
│  Side  │  Dashboard                                      │
│  bar   │                                                 │
│        │  [+ New Project]                    [Search...] │
│ >Dash  │                                                 │
│  Proj  │  ┌─────────────┐ ┌─────────────┐ ┌───────────┐│
│  Templ │  │ Project A   │ │ Project B   │ │ Project C ││
│  Sett  │  │ 12 sheets   │ │ 8 sheets    │ │ 3 sheets  ││
│  Bill  │  │ Updated 2h  │ │ Updated 1d  │ │ Updated 5d││
│        │  │ 3 members   │ │ 2 members   │ │ 1 member  ││
│        │  └─────────────┘ └─────────────┘ └───────────┘│
│        │                                                 │
│        │  ┌─────────────┐ ┌─────────────┐               │
│        │  │ Project D   │ │ Project E   │               │
│        │  │ ...         │ │ ...         │               │
│        │  └─────────────┘ └─────────────┘               │
└────────┴─────────────────────────────────────────────────┘
```

- **Project cards**: show project name, sheet count, last updated time, active member count
- **Grid layout**: responsive card grid, 3-4 columns depending on width
- **+ New Project button**: opens a dialog (project name, optional description)
- **Search**: filter projects by name
- Clicking a card opens the project and switches to the plan viewer

---

## Screen 2: Plan Viewer & Takeoff Workspace

The core working screen. This is where 90% of time is spent.

```
┌──────────────────────────────────────────────────────────────┐
│  Top Bar                                                     │
│  [◄ Back] [Project Name]  [Takeoff Toolbar]  [Avatars] [⚙] │
├────────┬────────────────────────────────┬────────────────────┤
│        │                                │                    │
│ Sheet  │                                │   Quantities       │
│ Index  │        Plan Viewer             │   Panel            │
│        │                                │                    │
│ ┌────┐ │   (zoomable/pannable canvas    │   ▼ Int Wall 8'    │
│ │A1.1│ │    showing the construction    │     Sheet A1.01    │
│ │    │ │    plan with takeoff           │       Meas 1: 320  │
│ └────┘ │    measurements overlaid)      │       Meas 2: 180  │
│ ┌────┐ │                                │     Sheet A1.02    │
│ │A1.2│ │                                │       Meas 3: 410  │
│ │    │ │                                │   ▼ Ext Wall       │
│ └────┘ │                                │     ...            │
│ ┌────┐ │                                │                    │
│ │M1.1│ │                                │                    │
│ │    │ │                                │                    │
│ └────┘ │                                │                    │
│        │ [Scale: 1/4" = 1'-0"]  [Zoom]  │                    │
├────────┴────────────────────────────────┴────────────────────┤
│  Status Bar: Condition: Interior Wall 8' | Tool: Linear | Measurements: 47 │
└──────────────────────────────────────────────────────────────┘
```

### Layout Zones

**Sheet Index Panel (left, ~200px)**
- Thumbnail previews of all sheets in the plan set
- Smart sheet names auto-detected from PDF (e.g., "A1.01 - First Floor")
- Click a thumbnail to switch sheets
- Current sheet highlighted with accent border
- Collapsible to save space

**Plan Viewer (center, fills remaining space)**
- The primary canvas where the construction plan is rendered
- Zoom/pan controls in the bottom-right corner (or floating)
- Scale indicator in the bottom-left
- Takeoff measurements rendered as colored overlays on the plan
- Live cursors from other users shown here
- Background: slightly lighter than app background to frame the plan
- No border radius on the canvas -- sharp edges for precision

**Quantities Panel (right, ~320px)**
- Grouped tree view of all measurements
- Collapsible/expandable condition groups
- Per-sheet subtotals nested under conditions
- Bidirectional linking: click a row to highlight on plan, click on plan to highlight row
- Override indicator for manually adjusted values
- Resizable via drag handle on the left edge
- Can be collapsed entirely for full-width plan viewing

**Takeoff Toolbar (in top bar, center)**
- Tool buttons: Select, Linear, Area, Count, Scale Calibration
- Active tool highlighted with accent background
- Current condition selector: dropdown showing condition name + color swatch
- Undo / Redo buttons
- Compact icon buttons (28px height) with tooltips

**Status Bar (bottom, 28px)**
- Current condition name and color
- Active tool name
- Measurement count for the current sheet
- Cursor coordinates on the plan (optional)
- Background: `--surface`, top border: `--border`

### Interaction Patterns

- **Tool selection**: click a tool in the toolbar, or use keyboard shortcuts (L = Linear, A = Area, C = Count, V = Select, S = Scale)
- **Condition switching**: dropdown in the toolbar, or number keys (1-9) for quick switch to the first 9 conditions
- **Drawing**: click on the plan to draw measurements (behavior depends on active tool)
- **Selection**: click a measurement to select it, showing edit handles and properties
- **Pan**: middle-click drag, or Space + left-click drag
- **Zoom**: scroll wheel, or Ctrl +/- , or pinch-to-zoom on trackpad
- **Context menu**: right-click on a measurement for quick actions (delete, change condition, properties)

---

## Screen 3: Condition Manager

A dialog or side panel for creating and managing conditions and their assemblies.

```
┌───────────────────────────────────────────────────┐
│  Conditions                          [+ New]      │
├───────────────────────────────────────────────────┤
│                                                   │
│  ● Interior Wall - 8' Drywall     Linear  1,250LF│
│  ● Exterior Wall - Brick          Linear    890LF│
│  ● Floor - Ceramic Tile           Area    3,200SF│
│  ● Ceiling - ACT                  Area    2,800SF│
│  ● Duplex Outlets                 Count     247EA│
│  ● GFCI Outlets                   Count      38EA│
│                                                   │
├───────────────────────────────────────────────────┤
│  Selected: Interior Wall - 8' Drywall             │
│                                                   │
│  Name:  [Interior Wall - 8' Drywall        ]     │
│  Type:  [Linear ▼]    Color: [● Purple ▼]        │
│  Unit:  [LF ▼]        Style: [── Solid ▼]        │
│                                                   │
│  Properties:                                      │
│    Height:    [8    ] ft                           │
│    Spacing:   [16   ] in (stud spacing)           │
│    Thickness: [4.875] in                          │
│                                                   │
│  Assembly Items:                    [+ Add Item]  │
│  ┌───────────────────────────────────────────┐    │
│  │ Drywall Sheets  │ sheets │ len*ht*2/32   │    │
│  │ Metal Studs     │ EA     │ len/(sp/12)+1 │    │
│  │ Drywall Screws  │ EA     │ len*ht*2*1.5  │    │
│  │ Joint Tape      │ LF     │ len*4         │    │
│  │ Joint Compound  │ gal    │ len*ht*2/100  │    │
│  └───────────────────────────────────────────┘    │
│                                                   │
│  [Import from Templates]    [Save]  [Cancel]      │
└───────────────────────────────────────────────────┘
```

- **Top section**: list of all conditions in the project, showing name, color dot, type, and current total
- **Bottom section**: detail editor for the selected condition
- **Formula editor**: inline text fields with autocomplete for variables (`len`, `ht`, `sp`, etc.)
- **Assembly items table**: editable inline table for adding/editing/removing items
- Can be opened as a side panel (pushes the quantities panel) or as a full dialog

---

## Screen 4: Settings

Organization and account settings in a clean, tabbed layout.

```
┌──────────────────────────────────────────────────────┐
│  Top Bar                                             │
├────────┬─────────────────────────────────────────────┤
│        │                                             │
│  Side  │  Settings                                   │
│  bar   │                                             │
│        │  [General] [Team] [Billing] [Account]       │
│        │  ─────────────────────────────────────      │
│  Dash  │                                             │
│  Proj  │  Organization Name                          │
│  Templ │  [Acme Construction LLC              ]      │
│ >Sett  │                                             │
│  Bill  │  Logo                                       │
│        │  [Upload Logo]  (or current logo preview)   │
│        │                                             │
│        │  Default Unit System                        │
│        │  (●) Imperial (ft, in, SF, LF)              │
│        │  ( ) Metric (m, cm, m², m)                  │
│        │                                             │
│        │  [Save Changes]                             │
│        │                                             │
└────────┴─────────────────────────────────────────────┘
```

- **General tab**: org name, logo, default units
- **Team tab**: member list, invite flow, role management, guest list
- **Billing tab** (Owner only): current plan, seat count, next renewal, payment method, invoice history
- **Account tab**: personal profile (name, email, password change)
- Clean, spacious forms -- this is the one place where generous whitespace is appropriate

---

## Screen 5: Export Dialog

Simple dialog triggered from the project toolbar.

```
┌───────────────────────────────────────┐
│  Export Quantities                     │
│                                       │
│  Format:                              │
│  (●) Excel (.xlsx)                    │
│  ( ) PDF                              │
│                                       │
│  Scope:                               │
│  Full Project (all conditions,        │
│  all sheets)                          │
│                                       │
│  Preview:                             │
│  • 12 conditions                      │
│  • 47 measurements                    │
│  • 8 sheets                           │
│                                       │
│          [Cancel]  [Export]            │
└───────────────────────────────────────┘
```

- Minimal dialog -- format choice and a summary of what will be exported
- Export button triggers server-side generation and file download
- Loading spinner while generating, then auto-download

---

## Screen 6: Welcome Modal (First Login)

```
┌───────────────────────────────────────────────┐
│                                               │
│  Welcome to Contruo                           │
│                                               │
│  Get started in 4 steps:                      │
│                                               │
│  1. Upload a plan                             │
│     Drop a PDF to start your takeoff          │
│                                               │
│  2. Create a condition                        │
│     Name it, pick a color, set the type       │
│                                               │
│  3. Start measuring                           │
│     Use Linear, Area, or Count tools          │
│                                               │
│  4. Review quantities                         │
│     Your measurements appear in the panel     │
│                                               │
│                          [Got it, let's go →] │
└───────────────────────────────────────────────┘
```

- Single modal, no multi-step carousel
- Clean typography, no images at MVP (add illustrations later)
- "Got it" button dismisses forever (set a flag in local storage / user profile)

---

## Screen 7: New Project Dialog

```
┌───────────────────────────────────────┐
│  New Project                          │
│                                       │
│  Project Name *                       │
│  [                                  ] │
│                                       │
│  Description (optional)               │
│  [                                  ] │
│                                       │
│  Upload Plans (optional)              │
│  ┌─────────────────────────────────┐  │
│  │  Drop PDF files here            │  │
│  │  or click to browse             │  │
│  └─────────────────────────────────┘  │
│                                       │
│          [Cancel]  [Create Project]   │
└───────────────────────────────────────┘
```

- Project name is required, everything else optional
- Can upload plans now or add them later
- Creating the project navigates to the plan viewer (or the plan upload step if no plans were added)

---

## UX Flow: Complete Takeoff Workflow

```
Login → Dashboard → New Project → Upload Plan(s) → Set Scale →
Create Conditions → Draw Measurements → Review Quantities → Export
```

1. **Login** -> lands on Dashboard
2. **Dashboard** -> click "+ New Project" -> enter name -> create
3. **Plan Viewer** -> upload PDF (drag-and-drop or file picker)
4. **Scale Calibration** -> prompted on first plan, draw known distance, enter real-world value
5. **Create Condition** -> open condition manager, define first condition
6. **Measure** -> select tool (Linear/Area/Count), draw on plan
7. **Review** -> check quantities panel, edit as needed
8. **Export** -> click Export, choose format, download

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `V` | Select tool |
| `L` | Linear takeoff tool |
| `A` | Area takeoff tool |
| `C` | Count takeoff tool |
| `S` | Scale calibration tool |
| `1-9` | Quick-switch to condition 1-9 |
| `Ctrl+Z` | Undo |
| `Ctrl+Shift+Z` | Redo |
| `Ctrl+E` | Export |
| `Space + drag` | Pan the plan |
| `Ctrl + scroll` | Zoom in/out |
| `Ctrl+F` | Search text in plan |
| `Delete` | Delete selected measurement |
| `Escape` | Cancel current drawing / deselect |
| `Enter` | Complete current measurement |
| `[` / `]` | Previous / next sheet |

---

## Notes

- The layout is intentionally dense and tool-like. Every competitive product (PlanSwift, OST, Bluebeam) is dense. Estimators expect density -- too much whitespace feels wasteful of screen real estate when you're trying to see the plan and quantities simultaneously.
- The three-panel layout (sheet index + plan viewer + quantities) can collapse to two panels or even one, but the default should show all three. Estimators using dual monitors may put the quantities on one screen and the plan on the other -- this is a future consideration.
- The status bar at the bottom is a small detail that matters: it gives constant feedback about what tool is active, what condition is selected, and how many measurements exist. Estimators often get lost in the flow and the status bar is a quick glance to reorient.
- Keyboard shortcuts are critical for power users. Estimators who use PlanSwift/OST are accustomed to keyboard-driven workflows. Not having shortcuts would be a dealbreaker.
