# Implementation Details Reference

## User Identity

Three app states, checked in `AppLayout`:
1. **needs-setup** — `GET /api/v1/persons/` returns < 2 → full-screen `SetupPage`
2. **needs-identity** — persons exist but `currentPersonId` is null/stale → full-screen `ProfilePicker`
3. **has-identity** — valid identity → main app shell with sidebar

- Identity persists in localStorage via Zustand (`couplefins:currentPersonId`)
- Sidebar shows both names with colored avatars — click inactive name to switch (1-click toggle, not dropdown)
- Upload page auto-selects person from identity store

## Dark/Light Mode

### Implementation
- Class-based: `@custom-variant dark (&:where(.dark, .dark *))` in `app.css`
- Three-way preference: system / light / dark, stored in localStorage as `couplefins:theme`
- FOIT prevention: synchronous `<script>` in `index.html` `<head>` reads localStorage + matchMedia, sets `.dark` class before first paint
- `color-scheme` property on `:root` (light) and `.dark` (dark) for native browser elements
- Theme management: `web/src/lib/theme.ts` — `getStoredTheme()`, `storeTheme()`, `resolveIsDark()`, `applyTheme()`

### Rules
- Use semantic tokens via `@theme` (NOT `@theme inline` — inline bakes values at build time, breaking dark mode)
- Prefer CSS variable swaps in `:root` / `.dark` over `dark:` utility prefixes
- Listen for `matchMedia` change events when in "system" mode

## Accessibility (WCAG 2.2)

Built into the existing codebase:
- **Focus rings**: Global rule in `app.css` — all interactive elements get `2px solid var(--ring)` on `focus-visible`
- **Skip-to-content**: `.skip-to-content` link in `AppLayout`, targets `#main-content`
- **Semantic HTML**: `<button>`, `<nav aria-label>`, `<main>`, `<aside aria-label>`, `<section>`
- **Touch targets**: Primary actions min 44px (`min-h-11`)
- **Async feedback**: `aria-live="polite"` on dynamic content
- **Headings**: Sequential hierarchy, never skip levels
- **Forms**: `<label>` via `htmlFor`, `aria-describedby` for errors, `role="alert"` on `InlineError`
- **Keyboard navigation**: Full support in `Combobox`, `SegmentedControl`, `MonthGrid`, filter popovers

## UI Audit Checklist

- [ ] Typography: Satoshi loaded? No Inter or system font visible?
- [ ] Numbers: `tabular-nums` on all financial figures? Right-aligned?
- [ ] Color: warm neutrals only, no pure black/white? Semantic teal/coral?
- [ ] Spacing: `space-y-6` between sections? Varied rhythm, not uniform?
- [ ] Depth: `shadow-sm` only? `rounded-xl` on cards, `rounded-lg` nested?
- [ ] States: `PageLoading`, `PageError`, `PageEmpty` for every async view?
- [ ] Dark mode: renders correctly in both modes? Native elements styled?
- [ ] Accessibility: contrast passes, focus visible, keyboard nav works?
- [ ] Finance: `formatCurrency()` used, amounts colored, status has icon + color?
- [ ] Copy: verb + object CTAs, neutral framing, no generic text?
- [ ] Components: using `Button`, `Card`, `baseInputClass`, `SegmentedControl` (not ad-hoc)?
- [ ] State: URL params for filters/dates, Zustand only for identity?
