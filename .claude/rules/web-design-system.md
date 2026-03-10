---
paths:
  - "web/src/components/**"
  - "web/src/pages/**"
  - "web/src/layouts/**"
  - "web/src/stores/**"
---
# Web Design System — Warm Personal Finance

Couplefins is a shared finance tool used monthly by a couple. The interface should feel
calm, personal, and trustworthy — like a well-organized notebook, not a corporate dashboard.
Prioritize clarity and scannability for financial data.

## Typography (enforce strictly)

**NEVER use Inter. It is banned from this project.**

- **UI font (Satoshi)**: all headings, labels, body text, buttons, navigation
- **Numbers (Satoshi tabular)**: financial figures use `font-variant-numeric: tabular-nums` for alignment
- **Mono font (Geist Mono)**: only for IDs, codes, technical identifiers — never for body text or numbers

Load Satoshi as a variable font from Fontshare. Load Geist Mono from Google Fonts or npm.

## Color Palette

### Base (warm neutrals)
- Background: warm off-white/cream (not pure white, not gray)
- Surface: slightly lighter or darker warm neutral for cards/sections
- Text: warm dark gray (not pure black)
- Muted text: medium warm gray

### Semantic (teal/coral)
- Positive/income/under-budget: teal (not green)
- Negative/expense/over-budget: coral (not red)
- Use muted variants for backgrounds, saturated for text/icons

### Accent
- One warm accent color for primary actions (buttons, links, focus states)
- Derive from teal or choose a complementary warm tone

## Spacing & Layout
- Generous whitespace — breathing room between sections
- Vary rhythm between sections (don't uniform-space everything)
- Card-based layout with gentle shadows (not flat, not heavy)
- Rounded corners (rounded-lg / rounded-xl) for a soft feel

## Depth System
- Subtle warm-toned shadows (not pure black shadows)
- 2-3 elevation levels max (flat, raised, modal)
- Borders: subtle, warm gray — not harsh dividers

## Motion
- 150ms for interactions (hover, focus, press)
- 200-300ms for layout transitions (expand, appear)
- Ease-out for entrances, ease-in for exits
- No gratuitous animation — motion should confirm actions

## Anti-Patterns (never do these)
- Never use Inter, Roboto, or Open Sans
- No indigo/blue/purple gradients
- No glassmorphism or frosted glass
- No uniform card grids with identical spacing
- No pure black (#000) or pure white (#fff) — always warm-shifted
- No animate-pulse skeleton loaders
- No native browser form controls unstyled in the design
- No decorative elements that serve no purpose

## User Identity

- Current person ID stored in localStorage via Zustand persist (`couplefins:currentPersonId`)
- Three app states:
  1. **needs-setup**: `GET /api/v1/persons/` returns < 2 people → full-screen SetupPage
  2. **needs-identity**: persons exist but `currentPersonId` is null or stale → full-screen ProfilePicker
  3. **has-identity**: persons exist and identity is valid → main app with shell
- ProfilePicker is a lightweight "click your name" screen (2 person cards) — NOT the SetupPage
- Sidebar shows user identity toggle: both names, active emphasized, click inactive to switch (1-click toggle, NOT a dropdown — only 2 users)
- Upload page auto-selects person from identity store — no "Who are you?" re-identification
- Never require re-identification on every page visit

## Dark/Light Mode

- `@custom-variant dark (&:where(.dark, .dark *))` in app.css for class-based control
- Semantic color tokens via `@theme` (NOT `@theme inline` for colors — inline bakes values at build time, breaking dark mode)
- Three-way preference: system / light / dark, stored in localStorage as `couplefins:theme`
- FOIT prevention: synchronous `<script>` in `<head>` (not `type="module"`, not `defer`) reads localStorage + matchMedia, sets `.dark` class on `<html>` before first paint
- `color-scheme` property on `:root` (light) and `.dark` (dark) for native browser elements (scrollbars, selects, form controls)
- Prefer CSS variable swaps over `dark:` utility prefixes — markup should rarely need `dark:` classes
- Listen for `matchMedia` change events when in "system" mode (user toggles OS while app is open)

## Information Architecture

Left sidebar with 5 pages: Dashboard / Transactions / Budget / Upload / Settings.
- "Transactions" (not "Reconciliation") — standard finance-app naming
- "Settings" absorbs person config, category management, and theme toggle
- "History" is NOT a standalone page — month navigation lives within Dashboard and Transactions
- Upload is lower in the nav (monthly task, not daily)

## UI Audit Checklist (run before marking any UI story as complete)

- [ ] Typography: Satoshi loaded and applied? No Inter/system font fallback visible?
- [ ] Numbers: `tabular-nums` on all financial figures?
- [ ] Color: warm neutrals only, no pure black/white, semantic teal/coral?
- [ ] Spacing: varied rhythm between sections, not uniform padding?
- [ ] Depth: warm shadows, 2-3 elevation levels, not all flat?
- [ ] States: empty, loading, error states for every list/table?
- [ ] Dark mode: renders correctly in both modes? Native elements styled?
- [ ] Accessibility: contrast ratios pass, focus indicators visible, keyboard nav works?
- [ ] Metadata: custom page title, custom favicon (not Vite default)?
- [ ] Finance: numbers right-aligned in tables, currency consistent, amounts colored?
- [ ] Copy: no generic placeholder text ("Welcome to..."), helpful error messages?
- [ ] No AI slop: no uniform card grids, no identical spacing, no purple gradients?
