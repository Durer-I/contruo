# Contruo Frontend Architecture

> **Status:** In Progress
> **Stack:** Next.js + React + TypeScript + Tailwind CSS + shadcn/ui + Liveblocks

---

## Tech Stack

| Technology | Purpose |
|-----------|---------|
| **Next.js 14+** | React framework with App Router, SSR, API routes |
| **React 18+** | UI component library |
| **TypeScript** | Type safety across the entire frontend |
| **Tailwind CSS** | Utility-first styling with custom dark theme |
| **shadcn/ui** | Accessible, customizable component primitives |
| **Liveblocks** | Real-time collaboration (presence, cursors, live sync) |
| **Lucide Icons** | Icon library (bundled with shadcn/ui) |
| **PDF.js / PSPDFKit** | PDF rendering in the plan viewer (evaluate during Sprint 05) |

---

## Project Structure

```
contruo-frontend/
├── app/                          # Next.js App Router
│   ├── layout.tsx                # Root layout (fonts, theme, providers)
│   ├── page.tsx                  # Landing/redirect to dashboard
│   │
│   ├── (auth)/                   # Auth pages (no sidebar)
│   │   ├── login/page.tsx
│   │   ├── signup/page.tsx
│   │   ├── reset-password/page.tsx
│   │   └── accept-invite/page.tsx
│   │
│   ├── (app)/                    # Authenticated app (sidebar + top bar)
│   │   ├── layout.tsx            # App shell: sidebar, top bar, main content
│   │   ├── dashboard/page.tsx    # Project cards grid
│   │   ├── settings/
│   │   │   ├── page.tsx          # General settings
│   │   │   ├── team/page.tsx     # Team members, invitations
│   │   │   ├── billing/page.tsx  # Subscription, seats, invoices
│   │   │   └── account/page.tsx  # Profile, password
│   │   └── project/[id]/
│   │       ├── layout.tsx        # Project workspace layout (sheet index + viewer + quantities)
│   │       └── page.tsx          # Plan viewer + takeoff workspace
│   │
│   └── api/                      # Next.js API routes (if needed for BFF pattern)
│
├── components/
│   ├── ui/                       # shadcn/ui components (auto-generated)
│   │   ├── button.tsx
│   │   ├── dialog.tsx
│   │   ├── dropdown-menu.tsx
│   │   ├── input.tsx
│   │   ├── table.tsx
│   │   ├── tooltip.tsx
│   │   └── ...
│   │
│   ├── layout/                   # App shell components
│   │   ├── app-shell.tsx         # Top bar + sidebar + main content wrapper
│   │   ├── top-bar.tsx           # Logo, project selector, toolbar, avatars, settings
│   │   ├── sidebar.tsx           # Navigation sidebar (collapsible)
│   │   └── status-bar.tsx        # Bottom bar (active tool, condition, zoom)
│   │
│   ├── auth/                     # Auth-related components
│   │   ├── login-form.tsx
│   │   ├── signup-form.tsx
│   │   └── welcome-modal.tsx
│   │
│   ├── dashboard/                # Dashboard components
│   │   ├── project-card.tsx
│   │   ├── project-grid.tsx
│   │   └── new-project-dialog.tsx
│   │
│   ├── viewer/                   # Plan viewer components
│   │   ├── plan-canvas.tsx       # Main PDF rendering canvas
│   │   ├── sheet-index.tsx       # Sheet thumbnails panel (left)
│   │   ├── viewport-controls.tsx # Zoom, fit-to-page, minimap
│   │   └── scale-calibration.tsx # Scale calibration tool UI
│   │
│   ├── takeoff/                  # Takeoff tool components
│   │   ├── toolbar.tsx           # Tool selection bar
│   │   ├── linear-tool.tsx       # Linear measurement drawing logic
│   │   ├── area-tool.tsx         # Area measurement drawing logic
│   │   ├── count-tool.tsx        # Count marker placement logic
│   │   ├── measurement-layer.tsx # Renders all measurements on the canvas
│   │   └── vertex-handles.tsx    # Draggable vertex edit handles
│   │
│   ├── conditions/               # Condition management components
│   │   ├── condition-manager.tsx # Full condition editor panel/dialog
│   │   ├── condition-list.tsx    # List of conditions with color dots
│   │   ├── condition-form.tsx    # Properties form (name, color, type, etc.)
│   │   ├── assembly-table.tsx    # Assembly items inline table
│   │   ├── formula-editor.tsx    # Formula input with autocomplete
│   │   ├── color-picker.tsx      # Preset + custom color picker
│   │   └── condition-selector.tsx # Toolbar dropdown for active condition
│   │
│   ├── quantities/               # Quantities panel components
│   │   ├── quantities-panel.tsx  # Main panel container
│   │   ├── quantity-tree.tsx     # Grouped tree view (virtualized)
│   │   ├── quantity-row.tsx      # Individual row (condition, sheet, measurement, assembly)
│   │   └── override-editor.tsx   # Inline override value editor
│   │
│   ├── collaboration/            # Collaboration components
│   │   ├── presence-avatars.tsx  # Online user avatar bar
│   │   ├── live-cursors.tsx      # Other users' cursor rendering
│   │   └── lock-indicator.tsx    # "Being edited by..." indicator
│   │
│   ├── export/                   # Export components
│   │   └── export-dialog.tsx     # Format selection + trigger
│   │
│   └── settings/                 # Settings page components
│       ├── org-settings-form.tsx
│       ├── team-table.tsx
│       ├── invite-dialog.tsx
│       ├── billing-summary.tsx
│       └── account-form.tsx
│
├── lib/                          # Shared utilities and services
│   ├── api.ts                    # FastAPI client (fetch wrapper with auth headers)
│   ├── supabase.ts               # Supabase client initialization
│   ├── liveblocks.ts             # Liveblocks client configuration
│   ├── auth.ts                   # Auth helpers (login, logout, session check)
│   ├── formula.ts                # Client-side formula parser (for live preview)
│   ├── geometry.ts               # Geometric calculations (area, perimeter, length)
│   ├── pdf.ts                    # PDF rendering helpers
│   ├── scale.ts                  # Scale calibration math (pixels <-> real-world units)
│   ├── keyboard.ts               # Keyboard shortcut manager
│   └── constants.ts              # App-wide constants (condition colors, units, etc.)
│
├── hooks/                        # Custom React hooks
│   ├── use-auth.ts               # Auth state and session management
│   ├── use-project.ts            # Current project data and operations
│   ├── use-measurements.ts       # Measurement CRUD operations
│   ├── use-conditions.ts         # Condition CRUD operations
│   ├── use-quantities.ts         # Aggregated quantity data for the panel
│   ├── use-canvas.ts             # Plan viewer canvas state (zoom, pan, viewport)
│   ├── use-active-tool.ts        # Current tool and drawing state
│   ├── use-keyboard.ts           # Keyboard shortcut registration
│   └── use-collaboration.ts      # Liveblocks presence, cursors, locks
│
├── providers/                    # React context providers
│   ├── auth-provider.tsx         # Authentication context
│   ├── project-provider.tsx      # Current project context
│   ├── liveblocks-provider.tsx   # Liveblocks room provider
│   └── theme-provider.tsx        # Theme context (dark mode)
│
├── types/                        # TypeScript type definitions
│   ├── project.ts                # Project, Plan, Sheet types
│   ├── condition.ts              # Condition, AssemblyItem types
│   ├── measurement.ts            # Measurement, Geometry, Vertex types
│   ├── user.ts                   # User, Role, Invitation types
│   └── api.ts                    # API response/request types
│
├── styles/
│   └── globals.css               # Tailwind directives + CSS custom properties (theme)
│
├── public/                       # Static assets
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── package.json
└── .env.local.example
```

---

## Routing Structure

| Route | Page | Layout |
|-------|------|--------|
| `/login` | Login form | Auth layout (centered, no sidebar) |
| `/signup` | Signup form (name, email, password, org name) | Auth layout |
| `/reset-password` | Password reset | Auth layout |
| `/accept-invite/:token` | Accept invitation, create account | Auth layout |
| `/dashboard` | Project cards grid | App layout (sidebar + top bar) |
| `/settings` | General org settings | App layout |
| `/settings/team` | Team members, invitations, guests | App layout |
| `/settings/billing` | Subscription, seats, invoices | App layout |
| `/settings/account` | Personal profile, password | App layout |
| `/project/:id` | Plan viewer + takeoff workspace | Project layout (3-panel) |

---

## State Management Strategy

Contruo uses **no global state library** (no Redux, Zustand, etc.). State is managed through three patterns:

### 1. Server State (API Data)

Data fetched from the FastAPI backend. Use **React Query (TanStack Query)** or **SWR** for:
- Projects list, project details
- Conditions and assembly items
- Measurements (fetched on project open, updated via mutations)
- Team members, invitations
- Billing data

Caching, revalidation, and optimistic updates handled by the library.

### 2. Collaboration State (Liveblocks)

Real-time shared state managed by Liveblocks:
- **Presence**: cursor position, active sheet, active tool, selected condition, locked measurement ID
- **Broadcast**: events for measurement created/edited/deleted, condition changes
- **Storage** (optional): live measurement data during active sessions for instant sync

Liveblocks provides React hooks: `useMyPresence()`, `useOthers()`, `useBroadcastEvent()`, etc.

### 3. Local UI State (React Context + Hooks)

Client-only state that doesn't sync or persist:
- Active tool (Select, Linear, Area, Count, Scale)
- Canvas viewport (zoom level, pan offset)
- Panel sizes and collapse state
- Drawing in-progress state (vertices placed so far)
- Selection state (which measurement is selected)
- Undo/redo stack

---

## Plan Viewer Canvas Architecture

The plan viewer is the most complex frontend component. It renders a PDF with interactive measurement overlays.

### Layer Stack

```
┌─────────────────────────────┐
│  Cursor Layer (top)         │  Live cursors from other users
├─────────────────────────────┤
│  UI Overlay Layer           │  Vertex handles, selection box, tooltips
├─────────────────────────────┤
│  Drawing Layer              │  In-progress measurement being drawn
├─────────────────────────────┤
│  Measurement Layer          │  All completed measurements (lines, areas, dots)
├─────────────────────────────┤
│  PDF Layer (bottom)         │  The construction plan itself
└─────────────────────────────┘
```

### Rendering Approach

- **PDF Layer**: rendered by the PDF library (pdf.js or PSPDFKit) into a canvas element
- **Measurement Layer**: rendered on a separate transparent canvas overlaying the PDF canvas
- **UI/Cursor Layers**: rendered as HTML/SVG overlays on top of the canvases

This separation allows:
- The PDF to be cached/rasterized independently
- Measurements to re-render without re-rendering the PDF
- UI elements (cursors, handles) to use DOM rendering for easier interaction handling

### Coordinate Systems

Two coordinate systems are in play:

- **Screen coordinates**: pixel position on the user's screen (affected by zoom/pan)
- **Plan coordinates**: position on the actual plan (independent of zoom/pan)

All measurement geometry is stored in **plan coordinates**. The canvas transform (zoom + pan offset) converts between the two. Liveblocks cursor positions are also in plan coordinates so they render correctly regardless of each user's viewport.

```
screen_x = (plan_x * zoom) + pan_offset_x
plan_x = (screen_x - pan_offset_x) / zoom
```

---

## API Client Pattern

A thin wrapper around `fetch` that handles auth headers and error parsing:

```typescript
// lib/api.ts
const api = {
  async get<T>(path: string): Promise<T> { ... },
  async post<T>(path: string, body: unknown): Promise<T> { ... },
  async patch<T>(path: string, body: unknown): Promise<T> { ... },
  async delete(path: string): Promise<void> { ... },
}
```

- Automatically includes `Authorization: Bearer <jwt>` header from Supabase session
- Automatically parses JSON responses
- Throws typed errors for non-200 responses
- Base URL from environment: `NEXT_PUBLIC_API_URL`

---

## Liveblocks Integration Pattern

```
app/(app)/project/[id]/layout.tsx
  └── LiveblocksProvider (room = "contruo:{orgId}:{projectId}")
        └── ProjectProvider (project data context)
              └── Plan Viewer + Quantities Panel + Collaboration UI
```

- The Liveblocks room is created at the project layout level
- All child components can use Liveblocks hooks (`useMyPresence`, `useOthers`, etc.)
- Auth token for Liveblocks is obtained from `POST /api/v1/liveblocks/auth` on the FastAPI backend

---

## Keyboard Shortcut System

Centralized keyboard shortcut manager in `lib/keyboard.ts`:

- Register shortcuts with handlers: `registerShortcut('L', () => setActiveTool('linear'))`
- Shortcuts are contextual: disabled when a text input is focused
- Conflict detection: warn in dev mode if a shortcut is registered twice
- Full shortcut list defined in `docs/design/screen-layouts.md`

Shortcuts are registered via the `useKeyboard()` hook at the workspace level.

---

## Performance Considerations

| Concern | Strategy |
|---------|----------|
| Large PDFs | Render visible viewport only, lazy-load pages |
| Many measurements (500+) | Canvas-based rendering (not DOM elements per measurement) |
| Quantities panel (1000+ rows) | Virtualized list (react-window or tanstack-virtual) |
| Real-time cursor updates | Throttled to 15Hz, client-side interpolation |
| Bundle size | Code splitting per route, lazy load PDF library |
| Zoom/pan smoothness | requestAnimationFrame for transforms, GPU-accelerated canvas |

---

## Environment Variables

```env
NEXT_PUBLIC_API_URL=http://localhost:8000     # FastAPI backend URL
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=xxx
NEXT_PUBLIC_LIVEBLOCKS_PUBLIC_KEY=xxx
```

All `NEXT_PUBLIC_` prefixed variables are available in the browser. Sensitive keys (service role keys, secrets) are backend-only and never exposed to the client.
