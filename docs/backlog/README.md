# Project Roadmap

## Version Matrix

| Version | Goal | Status | Effort |
|---|---|---|---|
| v0.1.0 | Project scaffold + data model + CSV parser + category groups | Completed (2026-03-09) | L |
| v0.1.1 | Upload flow (API + basic UI) | In Progress | M |
| v0.2.0 | Reconciliation engine + reconciliation page | Not Started | L |
| v0.2.1 | Dashboard + month navigation | Not Started | M |
| v0.3.0 | Adjustment export engine (per-person Monarch-importable CSVs) | Not Started | M |
| v0.3.1 | Export UI (download adjustments from reconciliation page) | Not Started | S |
| v0.4.0 | Budget tracking (monthly + YTD, set budgets, view progress) | Not Started | M |
| v0.4.1 | History & finalization (lock months, archive) | Not Started | S |

## Infrastructure Readiness

| Capability | v0.1.x | v0.2.x | v0.3.x | v0.4.x |
|---|---|---|---|---|
| FastAPI backend | ✅ | ✅ | ✅ | ✅ |
| SQLite + SQLAlchemy | ✅ | ✅ | ✅ | ✅ |
| CSV parsing | ✅ | ✅ | ✅ | ✅ |
| React frontend | ✅ | ✅ | ✅ | ✅ |
| Upload flow | ✅ | ✅ | ✅ | ✅ |
| Category groups | ✅ | ✅ | ✅ | ✅ |
| Reconciliation engine | — | ✅ | ✅ | ✅ |
| Dashboard | — | ✅ | ✅ | ✅ |
| Adjustment export | — | — | ✅ | ✅ |
| Budget tracking | — | — | — | ✅ |
| Month finalization | — | — | — | ✅ |

## Key Technical Decisions

- **Database**: SQLite via SQLAlchemy async (aiosqlite)
- **Backend**: FastAPI with Clean Architecture (domain / application / infrastructure / interface)
- **Frontend**: React 19 + Tailwind v4 + Tanstack Query, Orval codegen from OpenAPI
- **Auth**: None — two named profiles, select on upload
- **CSV source**: Monarch Money export (Date, Merchant, Category, Account, Original Statement, Notes, Amount, Tags)
- **Shared detection**: "shared" tag in Monarch CSV
- **Split ratios**: `sXX` tag (e.g., `s70` = payer pays 70%), default 50/50. Internally stored as `payer_person_id` + `payer_percentage` on each transaction — input-mechanism-agnostic
- **Category groups**: ~75 Monarch categories roll up into ~12 groups (e.g., "Groceries & Home Supplies" → "Food & Dining"). Budgets are set at the group level. Initial mapping seeded from JSON fixture on startup
- **Adjustment export**: Pure domain functions (no stored adjustment entities). Deterministic dedup IDs via UUID5 for idempotent Monarch re-import. `couplefins-adjustment` tag for filtering.
- **Tooling**: Poetry, Ruff, BasedPyright, pytest, Biome
