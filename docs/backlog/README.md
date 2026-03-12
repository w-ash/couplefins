# Project Roadmap

## Version Matrix

| Version | Goal | Status | Effort |
|---|---|---|---|
| v0.1.0 | Project scaffold + data model + CSV parser + category groups | Completed (2026-03-09) | L |
| v0.1.1 | Upload flow (API + basic UI) | Completed (2026-03-10) | M |
| v0.1.2 | Design foundations (fonts, warm theme, dark/light mode) | Completed (2026-03-10) | M |
| v0.1.3 | App shell, navigation, user identity & switching | Completed (2026-03-10) | M |
| v0.1.4 | UI audit & polish | Completed (2026-03-10) | S |
| v0.1.5 | Use case architecture refactor | Completed (2026-03-10) | M |
| v0.2.0 | Reconciliation engine + transactions page | Completed (2026-03-10) | L |
| v0.2.1 | Auto-create categories from CSV + category management UI | Completed (2026-03-10) | M |
| v0.2.2 | Dashboard + month navigation | Completed (2026-03-11) | M |
| v0.3.0 | Adjustment export engine (per-person Monarch-importable CSVs) | Completed (2026-03-11) | M |
| v0.3.1 | Export UI (download adjustments from transactions page) | Completed (2026-03-11) | S |
| v0.4.0 | Budget tracking (monthly + YTD, set budgets, view progress) | Completed (2026-03-12) | M |
| v0.4.1 | Month finalization (lock months, prevent changes) | Completed (2026-03-12) | S |

## Infrastructure Readiness

| Capability | v0.1.x | v0.2.x | v0.3.x | v0.4.x |
|---|---|---|---|---|
| FastAPI backend | ✅ | ✅ | ✅ | ✅ |
| SQLite + SQLAlchemy | ✅ | ✅ | ✅ | ✅ |
| CSV parsing | ✅ | ✅ | ✅ | ✅ |
| React frontend | ✅ | ✅ | ✅ | ✅ |
| Upload flow | ✅ | ✅ | ✅ | ✅ |
| Category groups | ✅ | ✅ | ✅ | ✅ |
| Design system (fonts, theme) | ✅ | ✅ | ✅ | ✅ |
| Dark/light mode | ✅ | ✅ | ✅ | ✅ |
| App shell / navigation | ✅ | ✅ | ✅ | ✅ |
| User identity (localStorage) | ✅ | ✅ | ✅ | ✅ |
| Reconciliation engine | — | ✅ | ✅ | ✅ |
| Dashboard | — | ✅ | ✅ | ✅ |
| Adjustment export (engine + UI) | — | — | ✅ | ✅ |
| Budget tracking | — | — | — | ✅ |
| Month finalization | — | — | — | ✅ |

## Key Technical Decisions

- **Database**: SQLite via SQLAlchemy async (aiosqlite)
- **Backend**: FastAPI with Clean Architecture (domain / application / infrastructure / interface)
- **Frontend**: React 19 + Tailwind v4 + Tanstack Query, Orval codegen from OpenAPI
- **Auth**: None — two named profiles, select on upload
- **User identity**: localStorage via Zustand persist (~1KB). Stores `currentPersonId` (UUID). Setup flow sets it, sidebar toggle switches it. Three app states: needs-setup, needs-identity, has-identity.
- **Information architecture**: Left sidebar with 5 pages: Dashboard / Transactions / Budget / Upload / Settings. "Transactions" replaces "Reconciliation" (standard finance-app naming). "Settings" absorbs person config + category management. "History" is not a standalone page — month navigation lives within Dashboard and Transactions.
- **Design system**: Satoshi font (Fontshare) + Geist Mono. Warm neutrals (not pure black/white), teal for positive, coral for negative. CSS custom properties via Tailwind v4 `@theme` for light/dark switching. Defined in `.claude/rules/web-design-system.md`.
- **Theme**: System preference by default (`prefers-color-scheme`), manual override stored in localStorage. Three-way: system/light/dark. Tailwind v4 class strategy with `@custom-variant dark`. Synchronous `<script>` in `<head>` prevents flash of wrong theme.
- **App shell**: Left sidebar navigation (industry standard for finance apps). React Router v7 `createBrowserRouter` with layout routes.
- **CSV source**: Monarch Money export (Date, Merchant, Category, Account, Original Statement, Notes, Amount, Tags)
- **Shared detection**: "shared" tag in Monarch CSV
- **Split ratios**: `sXX` tag (e.g., `s70` = payer pays 70%), default 50/50. Internally stored as `payer_person_id` + `payer_percentage` on each transaction — input-mechanism-agnostic
- **Category groups**: ~75 Monarch categories roll up into ~12 groups (e.g., "Groceries & Home Supplies" → "Food & Dining"). Budgets are set at the group level. Initial mapping seeded from JSON fixture on startup. New categories auto-created during CSV upload with `group_id=None` (unmapped). Users assign them to groups via Settings UI.
- **Adjustment export**: Pure domain functions (no stored adjustment entities). Deterministic dedup IDs via UUID5 for idempotent Monarch re-import. `couplefins-adjustment` tag for filtering.
- **Use case pattern**: Every use case has 3 objects — `Command` (frozen attrs, validated at construction), `Result` (frozen attrs), `UseCase` (`@define(slots=True)`, stateless). Uniform signature: `execute(self, command, uow) -> Result`. UoW passed to execute (not constructor). Transaction scoped via `async with uow:`. Even parameterless queries get an empty Command. Shared validators in `_shared/command_validators.py`.
- **Tooling**: uv, Ruff, BasedPyright, pytest, Biome
