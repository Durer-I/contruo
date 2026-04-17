# Contruo Design System

> **Status:** In Progress
> **Theme:** Dark, minimal, professional (Figma / Linear aesthetic)
> **Component Library:** shadcn/ui + Tailwind CSS
> **Accent Color:** Purple (placeholder -- final brand color TBD)

---

## Design Principles

1. **Minimal and focused** -- Every pixel on screen should serve a purpose. No decorative chrome, no gratuitous shadows, no visual noise. The construction plan is the hero; the UI is the frame.

2. **Information-dense without feeling cluttered** -- Estimators work with large amounts of data (hundreds of measurements, dozens of conditions). The UI must display density well with clear hierarchy, not hide information behind excessive clicks.

3. **Professional confidence** -- The product handles real money (bid estimates worth millions). The UI must feel precise, trustworthy, and stable. No playful animations, no casual fonts, no frivolous interactions.

4. **Tool-like, not website-like** -- Contruo is a professional tool, not a marketing page. Think Figma, AutoCAD, VS Code -- the UI should feel like an instrument, not a brochure. Dense toolbars, keyboard shortcuts, and efficient workflows over big buttons and whitespace.

5. **Dark-first** -- Dark theme as the default. Estimators stare at plans for hours; a dark surround reduces eye strain and makes the plan content (which is typically black lines on white paper) pop against the interface.

---

## Color Palette

### Background Layers (Dark Theme)

| Token | Hex | Usage |
|-------|-----|-------|
| `--background` | `#09090b` | App background (deepest layer) |
| `--surface` | `#0f0f12` | Panels, sidebars, cards |
| `--surface-raised` | `#18181b` | Elevated elements: modals, dropdowns, popovers |
| `--surface-overlay` | `#27272a` | Hover states, active sidebar items, selected rows |

### Foreground / Text

| Token | Hex | Usage |
|-------|-----|-------|
| `--foreground` | `#fafafa` | Primary text |
| `--foreground-muted` | `#a1a1aa` | Secondary text, labels, placeholders |
| `--foreground-subtle` | `#71717a` | Tertiary text, disabled states, hints |

### Accent (Purple -- Placeholder)

| Token | Hex | Usage |
|-------|-----|-------|
| `--accent` | `#8b5cf6` | Primary actions, selected states, active indicators |
| `--accent-hover` | `#7c3aed` | Hover state for accent elements |
| `--accent-muted` | `#8b5cf620` | Accent backgrounds (e.g., selected row highlight, accent badges) |
| `--accent-foreground` | `#ffffff` | Text on accent backgrounds |

### Borders

| Token | Hex | Usage |
|-------|-----|-------|
| `--border` | `#27272a` | Default borders (panels, cards, inputs) |
| `--border-hover` | `#3f3f46` | Hover-state borders |
| `--border-focus` | `#8b5cf6` | Focus ring color (uses accent) |

### Semantic Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `--success` | `#22c55e` | Success states, completed indicators |
| `--warning` | `#f59e0b` | Warnings, attention needed |
| `--error` | `#ef4444` | Errors, destructive actions, validation failures |
| `--info` | `#3b82f6` | Informational messages, links |

### Takeoff Condition Colors

These are the default colors available for conditions. They need to be visually distinct from each other and readable on both the dark UI and on white plan backgrounds.

| Name | Hex | Swatch |
|------|-----|--------|
| Red | `#ef4444` | Walls, structural |
| Blue | `#3b82f6` | Plumbing, water |
| Green | `#22c55e` | Landscaping, site |
| Orange | `#f97316` | Electrical |
| Purple | `#a855f7` | HVAC, mechanical |
| Yellow | `#eab308` | Finishes, paint |
| Cyan | `#06b6d4` | Fire protection |
| Pink | `#ec4899` | Insulation |
| Lime | `#84cc16` | Concrete, masonry |
| Indigo | `#6366f1` | Steel, metals |
| Teal | `#14b8a6` | Roofing |
| Rose | `#f43f5e` | Demolition |

---

## Typography

Using **Inter** -- the same font family used by Figma, Linear, and Vercel. Clean, highly legible at small sizes, excellent for data-dense interfaces.

| Token | Font | Size | Weight | Usage |
|-------|------|------|--------|-------|
| `--text-xs` | Inter | 11px | 400 | Smallest labels, badges |
| `--text-sm` | Inter | 13px | 400 | Secondary text, table cells, metadata |
| `--text-base` | Inter | 14px | 400 | Body text, form inputs, primary UI text |
| `--text-lg` | Inter | 16px | 500 | Section headers, panel titles |
| `--text-xl` | Inter | 18px | 600 | Page titles, modal headers |
| `--text-2xl` | Inter | 24px | 600 | Main headings (rare -- used in settings, onboarding) |
| `--text-mono` | JetBrains Mono | 13px | 400 | Formula editor, measurement values, code-like content |

### Typography Rules
- Use **medium (500)** weight for interactive labels (buttons, tabs, navigation items)
- Use **semibold (600)** sparingly -- only for headings and important numeric values
- Never use bold (700) in the UI -- it's too heavy for a minimal aesthetic
- Measurement values and quantities should use the mono font for alignment and precision feel
- Line height: 1.5 for body text, 1.2 for headings and labels

---

## Spacing System

Based on a **4px base unit**, consistent with Tailwind's default spacing scale.

| Token | Value | Usage |
|-------|-------|-------|
| `space-0.5` | 2px | Tight internal padding (badges, tiny gaps) |
| `space-1` | 4px | Minimal gaps between related elements |
| `space-2` | 8px | Standard inner padding (buttons, inputs, table cells) |
| `space-3` | 12px | Panel inner padding, card padding |
| `space-4` | 16px | Section spacing, gap between form fields |
| `space-6` | 24px | Major section dividers |
| `space-8` | 32px | Page-level padding, large section breaks |

### Spacing Rules
- **Dense by default** -- use `space-2` (8px) as the default gap between UI elements
- Panels and sidebars use `space-3` (12px) inner padding
- Tables use `space-2` (8px) cell padding for information density
- Never exceed `space-8` (32px) between elements -- keep things compact

---

## Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `--radius-sm` | 4px | Buttons, inputs, badges, small elements |
| `--radius-md` | 6px | Cards, panels, dropdowns |
| `--radius-lg` | 8px | Modals, dialogs, large containers |
| `--radius-full` | 9999px | Avatars, pills, circular buttons |

### Radius Rules
- Keep radius small and subtle. This is a professional tool, not a consumer app.
- Avoid excessive rounding -- no `rounded-xl` or `rounded-2xl` on functional elements
- The plan viewer canvas itself has **no border radius** (sharp corners for precision feel)

---

## Shadows & Elevation

Minimal use of shadows. The dark theme relies on **surface color layering** rather than shadows for elevation.

| Token | Value | Usage |
|-------|-------|-------|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.3)` | Subtle lift for dropdowns, tooltips |
| `--shadow-md` | `0 4px 12px rgba(0,0,0,0.4)` | Modals, dialogs, popovers |
| `--shadow-lg` | `0 8px 24px rgba(0,0,0,0.5)` | Command palette, major overlays |

### Elevation Rules
- Prefer **border + surface color change** over shadows for panel separation
- Shadows are reserved for floating elements only (dropdowns, modals, tooltips)
- Never apply shadows to inline/static elements

---

## shadcn/ui Component Customization

shadcn/ui provides unstyled, accessible components that we customize with our tokens. Key customizations:

### Buttons

| Variant | Background | Text | Border | Usage |
|---------|-----------|------|--------|-------|
| `primary` | `--accent` | `--accent-foreground` | none | Primary actions: "Save", "Create Project", "Export" |
| `secondary` | `--surface-raised` | `--foreground` | `--border` | Secondary actions: "Cancel", "Back" |
| `ghost` | transparent | `--foreground-muted` | none | Toolbar buttons, subtle actions |
| `destructive` | `--error` | white | none | Delete, remove actions |
| `outline` | transparent | `--foreground` | `--border` | Neutral outlined buttons |

- Buttons use `--text-sm` (13px) with `font-medium` (500)
- Padding: `space-2` (8px) vertical, `space-3` (12px) horizontal
- Height: 32px for default, 28px for compact (toolbar), 36px for large (onboarding)

### Inputs & Form Controls
- Height: 32px (compact, same as buttons)
- Background: `--surface`
- Border: `--border`, focus: `--border-focus` with subtle accent glow
- Text: `--foreground`, placeholder: `--foreground-subtle`
- No floating labels -- use labels above inputs (cleaner for dense forms)

### Tables (Quantities Panel)
- Row height: 32px (dense, maximizes visible data)
- Alternating row backgrounds: `--surface` / `--background` (subtle striping)
- Selected row: `--accent-muted` background
- Hover: `--surface-overlay` background
- Header: `--surface-raised` background, `--foreground-muted` text, `font-medium`
- Grid lines: `--border` horizontal only (no vertical lines for cleanliness)

### Sidebar / Navigation
- Background: `--surface`
- Active item: `--surface-overlay` background + left accent border (`--accent`)
- Hover: `--surface-overlay` background
- Icons: `--foreground-muted`, active: `--foreground`
- Width: 240px default, collapsible to 48px (icon-only)

### Dialogs / Modals
- Background: `--surface-raised`
- Overlay: `rgba(0,0,0,0.6)` backdrop
- Shadow: `--shadow-md`
- Max width: 480px for forms, 640px for complex dialogs
- Centered vertically and horizontally

### Tooltips
- Background: `--surface-raised`
- Text: `--foreground`
- Border: `--border`
- Shadow: `--shadow-sm`
- Delay: 500ms before showing (avoid tooltip noise)
- Max width: 240px

---

## Icons

Use **Lucide Icons** (the icon set bundled with shadcn/ui).

- Icon size: 16px for inline/toolbar, 20px for navigation, 24px for feature icons
- Icon color: `--foreground-muted` by default, `--foreground` when active/hovered
- Stroke width: 1.5px (default Lucide) -- matches the thin, precise aesthetic

---

## Animation & Motion

Minimal and purposeful. No decorative animations.

| Interaction | Duration | Easing | Notes |
|-------------|----------|--------|-------|
| Hover state transitions | 150ms | ease-out | Background color, border color changes |
| Panel expand/collapse | 200ms | ease-in-out | Sidebar, tree view expand |
| Modal appear | 150ms | ease-out | Fade + slight scale (0.98 -> 1.0) |
| Modal dismiss | 100ms | ease-in | Fade out only |
| Toast notifications | 200ms in, 150ms out | ease-out | Slide in from top-right |

### Motion Rules
- Never animate measurement drawing or plan navigation -- these must be instant
- Panel resizing (the split between plan viewer and quantities) has no animation -- direct drag
- Cursor presence (other users' cursors) uses smooth interpolation at 60fps for fluid movement

---

## Responsive Behavior

Contruo is a **desktop-first** application. Construction estimators work on desktop/laptop with large monitors.

| Breakpoint | Behavior |
|------------|----------|
| 1440px+ | Full layout: sidebar + plan viewer + quantities panel |
| 1024-1439px | Sidebar collapsible, plan and quantities adjust |
| < 1024px | Not supported at MVP -- show a "please use a desktop" message |

- Minimum supported resolution: 1280 x 720
- Optimized for: 1920 x 1080 (most common estimator setup)
- No mobile or tablet support at MVP

---

## Dark Theme Implementation (Tailwind + shadcn)

The dark theme is implemented using CSS custom properties in the `:root` selector and Tailwind's `darkMode: "class"` strategy:

```css
:root {
  --background: 240 6% 4%;
  --foreground: 0 0% 98%;
  --card: 240 5% 6%;
  --card-foreground: 0 0% 98%;
  --popover: 240 5% 10%;
  --popover-foreground: 0 0% 98%;
  --primary: 263 70% 66%;
  --primary-foreground: 0 0% 100%;
  --secondary: 240 4% 16%;
  --secondary-foreground: 0 0% 98%;
  --muted: 240 4% 16%;
  --muted-foreground: 240 5% 65%;
  --accent: 240 4% 16%;
  --accent-foreground: 0 0% 98%;
  --destructive: 0 84% 60%;
  --destructive-foreground: 0 0% 98%;
  --border: 240 4% 16%;
  --input: 240 4% 16%;
  --ring: 263 70% 66%;
  --radius: 0.375rem;
}
```

Values are in HSL format (without `hsl()` wrapper) as required by shadcn/ui's theming system.
