# Component Library Reference

All components live in `web/src/components/`.

## Primitives

| Component | Purpose | Key props |
|---|---|---|
| `Button` | Primary actions | `variant` (primary/secondary/destructive), `size` (default/sm), `loading`, `loadingText`, `icon`, `fullWidth` |
| `Card` | Container with border + shadow | `as` (div/section/form/aside), `className` |
| `SegmentedControl` | Radio toggle with sliding indicator | `options` (with optional icons), `value`, `onChange`, `size` (sm/default), `shape` (rounded/pill) |
| `Combobox` | Accessible select with search | `mode` (single/multi), `options`, `value`, `onChange`, `allowCreate` |
| `PercentInput` | 0-100 number input | `value`, `onChange`, `error`, `errorMessage` |
| `PersonBadge` | Colored name badge | `name`, `accentColor`, `size` (xs/sm/base/lg) |
| `InlineError` | Field-level error with icon | `children` |

## Navigation & Layout

| Component | Purpose |
|---|---|
| `Sidebar` | Left nav (w-56), wordmark, 7 `NavItem`s, identity toggle |
| `NavItem` | Sidebar link with icon, active: `border-l-2 bg-accent font-semibold` |
| `PageHeader` | Title + icon, optional right-side children for controls |
| `AppLayout` | Shell: `flex min-h-screen` with `Sidebar` + `<main>` outlet |

## Date & Filters

| Component | Purpose |
|---|---|
| `MonthPicker` | Month/year selector popover with `MonthGrid` |
| `MonthGrid` | 12-month grid with year navigation |
| `DateRangePicker` | Start/end date range selection |
| `TransactionFilters` | Payer, category, tag, amount range filters with active pills |

## Page States (`PageStates.tsx`)

| Component | When | Renders |
|---|---|---|
| `PageLoading` | Data fetching | Spinner + contextual label |
| `PageError` | API failure | Error message + retry button |
| `PageEmpty` | No data | Icon + heading + description + CTA link |

## Display

| Component | Purpose |
|---|---|
| `StatsGrid` | KPI card grid (3 cols if ≤ 3 items, else 2/4 responsive) |
| `UploadStatusRow` | Per-person upload status (pending/done) |
| `FinalizationBanner` | Lock state with icon |
| `UnmappedCategoriesWarning` | Alert with link to Settings |
| `ThemeToggle` | Light/dark/system radio with icons |

## Input Styles (`web/src/lib/input-styles.ts`)

Shared Tailwind class strings for consistent form elements:
- `baseInputClass` — Standard text input: `rounded-lg border border-input bg-card px-3 py-2 text-sm shadow-sm` with focus ring
- `selectInputClass` — Same as base but `py-1.5`
- `percentInputClass` — `w-16 tabular-nums` + baseInputClass
- `triggerButtonClass` — Dropdown trigger (inline-flex, gap, border, shadow, hover:bg-muted)
- `actionLinkClass` — Card-styled action link
- `inputErrorClass` — `border-negative focus:border-negative focus:ring-negative`

Use these instead of writing raw Tailwind for inputs.

## Icon Library

**lucide-react** (v0.577.0). All icons come from this package.

Nav icons: `LayoutDashboard`, `ArrowLeftRight`, `HandCoins`, `PieChart`, `TrendingUp`, `Upload`, `Settings`

Category group icons registered in `lib/category-icons.ts` — 19 icons mapped by name string. Use `getCategoryGroupIcon(iconName)` to resolve; defaults to `Tag` icon.
