---
name: web-design-reference
description: Design system reference for Couplefins web UI. Use when building or modifying frontend components, pages, or layouts — covers design intent, color tokens, component library, and UI patterns.
user-invocable: false
---

# Web Design System Reference

## Design Intent

Couplefins is a monthly-use tool for a couple reconciling shared expenses — opened briefly, together, over coffee. The interface should feel like a well-organized notebook: **calm, personal, trustworthy**. Financial data should inform, not stress.

Four principles guide every decision:

**Warm over clinical.** Financial apps default to cold precision. This app is about a relationship. Cream backgrounds, teal/coral semantics, Satoshi's humanist geometry, rounded surfaces — every material choice favors warmth over sterility. The warm hue shift (`oklch(... 85)` angle) carries through every neutral, including dark mode.

**Informative, not alarming.** Teal and coral replace green and red. Green/red triggers traffic-light associations (good/bad, go/stop) that turn every expense into a small judgment. Teal and coral communicate direction without the emotional weight. The settlement card states a fact ("Alice owes Bob $127.50"), not an alert.

**Clarity over density.** Two users, once a month. The interface can afford generous whitespace and progressive disclosure. Who-owes-whom is the hero element. Category breakdowns expand on demand. Tables show essential columns, not every field the API returns.

**Presence over authentication.** Both partners are always visible in the sidebar, switchable in one click. No login wall — this is a trusted-device, two-person tool. The sidebar makes the couple nature spatially obvious even when only one person is using it.

Full design rationale: `docs/ui-identity.md`. Enforcement rules (anti-patterns): `.claude/rules/web-design-system.md`.

---

## Typography

**Satoshi** (variable, from Fontshare) handles all UI text — geometric precision with humanist personality. **Inter is banned.** **Geist Mono** only for technical identifiers (IDs, codes), never amounts or body text. Financial figures: Satoshi with `tabular-nums`.

- `--font-sans: "Satoshi", ui-sans-serif, system-ui, sans-serif`
- `--font-mono: "Geist Mono", ui-monospace, SFMono-Regular, Menlo, monospace`

## Color

OKLCH throughout. **Warm neutrals** (hue-85 shift, never pure black/white). **Teal** = primary + positive. **Coral** = destructive + negative. **Amber** = warning.

| Token | Light | Dark | Tailwind |
|---|---|---|---|
| `--background` | `oklch(0.985 0.003 85)` | `oklch(0.175 0.006 58)` | `bg-background` |
| `--foreground` | `oklch(0.268 0.006 58)` | `oklch(0.93 0.004 85)` | `text-foreground` |
| `--primary` | `oklch(0.525 0.105 175)` | `oklch(0.575 0.1 175)` | `bg-primary`, `text-primary` |
| `--destructive` | `oklch(0.577 0.15 27)` | `oklch(0.63 0.17 27)` | `bg-destructive` |
| `--warning` | `oklch(0.666 0.14 55)` | `oklch(0.72 0.14 55)` | `bg-warning` |
| `--positive` | = primary teal | `oklch(0.65 0.1 175)` | `text-positive` |
| `--negative` | = destructive coral | `oklch(0.65 0.14 27)` | `text-negative` |

Muted variants: `*-muted` (background), `*-muted-foreground` (text), `*-border`. Structure: `--border`, `--border-muted`, `--input`, `--ring`, `--placeholder`, `--icon-muted`.

**Identity colors** — three semantic tokens for distinguishing spending sources:

| Token | Hue | Color | Meaning | Tailwind |
|---|---|---|---|---|
| `--household` | 175 | teal | Shared/household spending — same as primary | `bg-household`, `text-household-muted-foreground` |
| `--person-0` | 230 | blue | First person's individual spending | `bg-person-0`, `bg-person-0-muted` |
| `--person-1` | 290 | violet | Second person's individual spending | `bg-person-1`, `bg-person-1-muted` |

Cool-tone triad, ~55-60° apart. Person index is creation-order (deterministic). Used in budget category bars (stacked segments), person badges, sidebar identity toggle, transaction payer pills, and Insights "Who's paying" charts. Utilities: `getPersonAccentColor(index)` from `types/person.ts`, `usePersonMaps()` from `lib/persons.ts`.

All tokens in `web/src/app.css` `:root` (light) and `.dark` (dark), mapped via `@theme`.

## Page Layout

Content floats centered, reinforcing the notebook metaphor. Generous whitespace signals "take your time."

- Standard: `mx-auto max-w-4xl px-6 py-12`
- Settings: `max-w-3xl`. Upload: toggles `max-w-3xl`/`max-w-5xl`. Full-screen flows: `max-w-md`
- Page skeleton: `PageHeader` → `PageLoading`/`PageError`/`PageEmpty` → `space-y-6` content
- Rhythm: `space-y-6` between sections, `space-y-4` within cards, `space-y-1` for tight lists
- Varied spacing — uniform grids signal template, not craft

## Depth & Borders

Cards are paper in a notebook. Shallow depth: flat → raised → popover.

- Cards: `rounded-xl border border-border bg-card p-6 shadow-sm`
- Nested: `rounded-lg`
- `shadow-sm` only. `border-border` structural, `border-border-muted` subtle. No glassmorphism.

## Motion

Motion confirms actions, doesn't decorate. Animation novelty wears off fast in a monthly tool.

- 150ms for color transitions. 200-300ms for layout shifts. Ease-out in, ease-in out.
- `.editor-enter` keyframe (250ms grid expand) for detail panels.

## Finance Display

Every amount colored: `text-positive` (teal) / `text-negative` (coral) — the app's visual fingerprint.

- Numbers: right-aligned, `tabular-nums`, bold key metrics
- Currency: `formatCurrency()` from `lib/format.ts`
- Status: always color + icon, never color alone
- Budget health: `on_track` → teal, `near_limit` → amber, `over_budget` → coral
- Settlement card is the hero element, never buried. Person names, not "you/them."

## Voice & Microcopy

Plain language, factual, no celebration. "Import Complete" with a summary, not "Great job!"

- CTAs: verb + object ("Upload CSV", "Record Payment"). Never "Submit" or "OK".
- Neutral framing: "$847 of $900" not "almost over budget!" Financial data informs; it doesn't scold.
- Empty states: state what's missing, then say what to do. Never blank.
- Domain terms stay in code; UI says "shared," "personal," "split."

## Information Architecture

7-page sidebar: Dashboard / Transactions / Settle Up / Budget / Insights / Upload / Settings. Ordered by workflow frequency. "History" is NOT a standalone page.

---

## Detailed References

These files load on-demand — read them when you need specifics:

- **[Component library](components.md)** — All shared components with props, input styles, icon library
- **[Utilities & state management](utilities.md)** — URL-driven state hooks, data fetching pattern, Tanstack Query, utility module reference
- **[Implementation details](implementation.md)** — User identity states, dark mode implementation, accessibility baseline, UI audit checklist
