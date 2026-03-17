---
name: web-design-reference
description: Full design system reference for Couplefins web UI — spacing, motion, identity, dark mode, accessibility, finance patterns, and audit checklist
user-invocable: false
---

# Web Design System Reference

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

## User Identity
- Current person ID stored in localStorage via Zustand persist (`couplefins:currentPersonId`)
- Three app states:
  1. **needs-setup**: `GET /api/v1/persons/` returns < 2 people → full-screen SetupPage
  2. **needs-identity**: persons exist but `currentPersonId` is null or stale → full-screen ProfilePicker
  3. **has-identity**: persons exist and identity is valid → main app with shell
- ProfilePicker is a lightweight "click your name" screen (2 person cards) — NOT the SetupPage
- Sidebar shows user identity toggle: both names, active emphasized, click inactive to switch (1-click toggle, NOT a dropdown — only 2 users)
- Upload page auto-selects person from identity store — no "Who are you?" re-identification

## Dark/Light Mode
- `@custom-variant dark (&:where(.dark, .dark *))` in app.css for class-based control
- Semantic color tokens via `@theme` (NOT `@theme inline` for colors — inline bakes values at build time, breaking dark mode)
- Three-way preference: system / light / dark, stored in localStorage as `couplefins:theme`
- FOIT prevention: synchronous `<script>` in `<head>` (not `type="module"`, not `defer`) reads localStorage + matchMedia, sets `.dark` class on `<html>` before first paint
- `color-scheme` property on `:root` (light) and `.dark` (dark) for native browser elements
- Prefer CSS variable swaps over `dark:` utility prefixes
- Listen for `matchMedia` change events when in "system" mode

## Information Architecture
Left sidebar with 6 pages: Dashboard / Transactions / Settle Up / Budget / Upload / Settings.
- "Transactions" (not "Reconciliation")
- "Settle Up" between Transactions and Budget (monthly workflow: view → settle → review)
- "Settings" absorbs person config, category management, theme toggle
- "History" is NOT a standalone page — month navigation within Dashboard and Transactions
- Upload is lower in nav (monthly task, not daily)

## Self-Evidence & Microcopy
- Progressive disclosure: show information contextually, not all at once
- Affordances: interactive elements must look interactive (shadow, border, hover state)
- Action-oriented CTAs: verb + object ("Upload CSV", "Confirm Import"), never generic
- Plain language: "Alice's share" not "payer allocation percentage"
- Empty states: meaningful heading + one sentence of context + clear CTA
- Error messages: actionable, next to the field, no technical jargon
- Contextual help: tooltips for domain terms (payer percentage, split ratio)

## Component States
Every interactive component must handle all applicable states:
- **Empty**: guidance text + CTA (never blank)
- **Loading**: spinner or skeleton with contextual label
- **Error**: inline, actionable, adjacent to field, `aria-live="polite"`
- **Success**: explicit confirmation with summary
- **Hover/Focus**: visible on all interactive elements
- **Disabled**: `opacity-50 cursor-not-allowed`, visually distinct

## Accessibility Baseline (WCAG 2.2)
- Semantic HTML: `<button>`, `<nav>`, `<main>`, `<aside>`, `<section>`
- Focus rings: all interactive elements via base CSS rule in `app.css`
- Touch targets: primary actions min 44px (`min-h-11`)
- `aria-live="polite"` for async feedback
- Heading hierarchy: sequential, never skip levels
- Form inputs: `<label>` via `htmlFor` + `aria-describedby` for errors
- Skip-to-content link in app shell layout
- `aria-label` on landmark elements

## Finance Display Patterns
- Numbers: right-aligned, `tabular-nums`, bold key metrics
- Currency: `Intl.NumberFormat("en-US", { style: "currency", currency: "USD" })` everywhere
- Positive amounts: `text-positive` (teal). Negative: `text-negative` (coral)
- Status: always color + icon, never color alone

## UI Audit Checklist
- [ ] Typography: Satoshi loaded? No Inter/system font fallback visible?
- [ ] Numbers: `tabular-nums` on all financial figures?
- [ ] Color: warm neutrals only, no pure black/white, semantic teal/coral?
- [ ] Spacing: varied rhythm, not uniform padding?
- [ ] Depth: warm shadows, 2-3 elevation levels?
- [ ] States: empty, loading, error for every list/table?
- [ ] Dark mode: renders correctly in both modes? Native elements styled?
- [ ] Accessibility: contrast passes, focus visible, keyboard nav works?
- [ ] Finance: numbers right-aligned, currency consistent, amounts colored?
- [ ] Copy: no generic placeholder text, helpful error messages?
- [ ] No AI slop: no uniform grids, no identical spacing, no purple gradients?
- [ ] Component reuse: `<Button>`, `baseInputClass`, `<SegmentedControl>` used consistently?
- [ ] Card radius: top-level `rounded-xl`, nested `rounded-lg`?
