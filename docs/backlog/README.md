# Project Roadmap

## Getting Started (macOS)

### Prerequisites

Install these if you don't have them:

```bash
# Homebrew (skip if already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Python 3.14 via uv (Python version manager + package manager)
brew install uv

# Node.js 22+ via fnm (fast Node version manager)
brew install fnm
fnm install 22
fnm use 22

# pnpm (frontend package manager)
brew install pnpm
```

### Clone and set up

```bash
# 1. Clone
git clone git@github.com:w-ash/couplefins.git
cd couplefins

# 2. Install Python dependencies (creates .venv automatically)
uv sync

# 3. Create your .env from the example
cp .env.example .env
```

Edit `.env` and set your Neon PostgreSQL connection string:

```
DATABASE__URL=postgresql+asyncpg://user:pass@ep-xxxx.us-west-2.aws.neon.tech/dbname?sslmode=require
```

To get a connection string: create a free project at [neon.tech](https://neon.tech), copy the connection string from the dashboard, and replace `postgresql://` with `postgresql+asyncpg://`.

```bash
# 4. Run database migrations
uv run alembic upgrade head

# 5. Install frontend dependencies
pnpm --prefix web install

# 6. Generate TypeScript API client from OpenAPI spec
pnpm --prefix web generate

# 7. Start the local Postgres 18 container for integration tests
#    (compose file in repo root; matches TEST_DATABASE__URL in .env.example).
docker compose up -d
```

### Run the app

```bash
pnpm dev
```

This starts both servers concurrently:
- **API**: http://localhost:8001 (FastAPI with hot reload)
- **Web**: http://localhost:5174 (Vite dev server)

On first load, the app shows a setup screen to create both person profiles.

### Verify everything works

```bash
# Backend: lint, type check, dead code, tests
uv run ruff check . --fix && uv run ruff format . && uv run basedpyright src/ && uv run vulture && uv run pytest

# Frontend: lint, type check, build, tests
pnpm --prefix web check && pnpm --prefix web test
```

---

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
| v0.5.0 | Transaction split editing (individual + bulk) | Completed (2026-03-12) | M |
| v0.5.1 | Transaction field editing + audit log | Completed (2026-03-12) | M |
| v0.5.2 | Solo prep polish, settlement card hero & category icons | Completed (2026-03-13) | M |
| v0.5.3 | Plain language & verb+object CTAs | Completed (2026-03-13) | S |
| v0.5.4 | Guardrails: empty, loading, error states | Completed (2026-03-13) | S |
| v0.5.5 | Transaction search, filtering & date range | Completed (2026-03-13) | L |
| v0.6.0 | Settlement page, recording & bulk editing | Completed (2026-03-15) | L |
| v0.6.1 | Settlement history (Dashboard enrichment) | Completed (2026-03-16) | S |
| v0.6.2 | Code quality cleanup (DRY, consistency) | Completed (2026-03-16) | S |
| v0.6.3 | DRY enforcement & month navigation | Completed (2026-03-16) | M |
| v0.6.4 | Orval codegen activation + MSW test infrastructure | Completed (2026-03-16) | M |
| v0.7.0 | Spending trends — small multiples charts + Insights page | Completed (2026-03-17) | L |
| v0.7.1 | Comparison cards, budget lines & settlement balance trend | Completed (2026-03-17) | M |
| v0.7.2 | Year-over-year overlay, dark mode charts & drill-down | Completed (2026-03-17) | M |
| v0.8.0 | Responsive upload layout (mobile + desktop) | Completed (2026-03-17) | M |
| v0.8.1 | Drag-and-drop file zone | Completed (2026-03-17) | S |
| v0.8.2 | Upload history (endpoint + UI) | Completed (2026-03-17) | M |
| v0.8.3 | CSV validation & error quality (client + server) | Completed (2026-03-18) | M |
| v0.8.4 | Confirmation & flow polish | Completed (2026-03-18) | S |
| v0.8.5 | Insights page UX overhaul — controls, KPI hierarchy, "Who's paying" | Completed (2026-03-18) | L |
| v0.9.0 | Split continuum + `household` flag + spotted detection | Completed (2026-03-18) | M |
| v0.9.1 | Category entity + `include_personal` budget scope | Completed (2026-03-18) | M |
| v0.9.2 | Classification UI: filters, type editing, preview polish | Completed (2026-03-18) | M |
| v0.9.3 | Transaction exclusion flag | Completed (2026-03-18) | S |
| v0.10.0 | App shell + shared component mobile foundations | Completed (2026-03-19) | M |
| v0.10.1 | Content pages mobile layouts (Dashboard, Transactions, Settle Up) | Completed (2026-03-20) | L |
| v0.10.2 | Settings page overhaul (desktop + mobile quality) | Completed (2026-03-20) | M |
| v0.10.3 | Interaction consistency + touch polish | Completed (2026-03-21) | M |
| v0.11.0 | Auth backend (name+password, JWT cookies, protected routes) | Completed (2026-03-24) | M |
| v0.11.1 | Auth frontend (login page, setup flow, session management) | Completed (2026-03-25) | M |
| v0.11.2 | Personal budget backend (per-person limits, spending computation) | Completed (2026-03-26) | M |
| v0.11.3 | Scope UI (budget toggle, transaction scope filter) | Completed (2026-03-26) | L |
| v1.0.0 | PostgreSQL migration — Neon, asyncpg, JSONB+GIN, data migration | Completed (2026-03-27) | M |
| v1.0.1 | Multi-user readiness — smart polling, SSE event bus, index audit | Completed (2026-03-28) | M |
| v1.0.2 | Query optimization — Neon pool tuning, query batching, tag filtering | Completed (2026-03-28) | M |
| v1.0.3 | DRY audit, DB-backed theme preference, auth UX, sslmode fix | Completed (2026-03-28) | M |
| v1.0.4 | Structured logging — loguru → structlog, request middleware, JSON logs | Completed (2026-03-30) | S |
| v1.1.0 | Notes, discuss elevation, case-insensitive tags, editor & layout polish | Completed (2026-03-31) | M |
| v1.1.1 | Schema version guard — health endpoint versioning, upgrade screen | Completed (2026-03-31) | S |
| v1.2.0 | Scoped dashboard — household/personal/all toggle, budget alerts, self-documenting metrics | Completed (2026-04-01) | M |
| v1.2.1 | Terminology cleanup — "shared" → "household" throughout codebase, remove `TransactionType` | Completed (2026-04-01) | M |
| v1.2.2 | Settlement transaction linking — candidate matching, Settle Up linking UI | Completed (2026-04-03) | M |
| v1.2.3 | Brand identity — CoupleFins logo, favicon, Lucide v1 upgrade, lighter strokes | Completed (2026-04-03) | S |
| v1.2.4 | Transaction-first settlement flow — link transactions instead of recording payments | Completed (2026-04-04) | M |
| v1.3.0 | Per-month budget model — replace cascading effective dates with year/month | Completed (2026-04-04) | M |
| v1.3.1 | Copy from last month + budget page UX polish | Completed (2026-04-06) | S |
| v1.3.2 | Budget trends on Insights page — budget overlay lines on spending charts | Completed (2026-04-07) | M |
| v1.3.3 | Accounting guardrails — rounding fix, zero-sum assertion, settlement link validation, pre-finalization warnings | Completed (2026-04-05) | M |
| v1.3.4 | Monetary type consistency, budget/adjustment invariants, settlement amount validation | Completed (2026-04-06) | M |
| v1.3.5 | Graceful degradation, zero-tolerance type safety, error handling split | Completed (2026-04-06) | M |
| v1.3.6 | UI component library DRY — cn() utility, InlineSuccess, SectionHeader, heroCardClass, Card typing fix | Completed (2026-04-07) | S |
| v1.4.0 | Edit attribution — `edited_by_person_id` on TransactionEdit, threaded through all edit use cases | Completed (2026-04-07) | S |
| v1.4.1 | Import provenance — enriched edit history endpoint with upload-derived import event | Completed (2026-04-08) | S |
| v1.4.2 | Transaction history timeline — vertical timeline UI with import anchor + person-attributed edits | Completed (2026-04-08) | M |
| v1.5.0 | Chat assistant — right-edge panel, read-only queries via Claude API, mobile full-screen page, suggested questions | Completed (2026-04-10) | L |
| v1.5.1 | Chat UX polish — streaming markdown, tool-call result cards | Completed (2026-04-10) | S |
| v1.5.2 | Chat mutations — budget updates, transaction edits with confirmation cards | Completed (2026-04-10) | M |
| v1.5.3 | Chat hardening — architecture layering fix, integration tests, rate limiting, input safety | Completed (2026-04-10) | M |
| v1.5.4 | Chatbot voice — composable voice system, Fiona character, per-user voice setting | Completed (2026-04-10) | S |
| v1.5.5 | Chat UX affordances — new conversation, copy message, regenerate last reply, friendly limit error | Completed (2026-04-12) | S |
| v1.6.0 | Settle Up audit table + Transactions buckets — payer-split ledger, "Showing the work" narrative, spotted scope, header cards | Completed (2026-05-02) | L |
| v1.6.1 | Audit table & header-card correctness follow-ups — settled-state honesty, derived totals, link targets | Completed (2026-07-02) | S |
| v1.7.0 | Settlement correctness — waiver fix, settlement scope, sXX precedence, finalization guards | Completed (2026-07-03) | L |
| v1.7.1 | Upload & re-upload integrity — true replace, flag preservation, dedup window, parser hardening | Completed (2026-07-03) | M |
| v1.7.2 | Budget & dashboard math — sign-aware spending, YTD totals, unmapped visibility, copy-budgets gate | Completed (2026-07-03) | M |
| v1.7.3 | Insights & chat accuracy — comparison cards, settled trend, YTD cutoff, chat scope & local dates | Completed (2026-07-03) | M |
| v1.7.4 | Guardrails & DRY — shared exclusion predicate, suppression removal, fixture realism | Completed (2026-07-03) | S |
| v1.7.5 | Settlement ledger — running outstanding balance, multi-month catch-ups, derived month status | Completed (2026-07-04) | L |
| v1.8.0 | Agentic chat foundations — Opus 4.8 + adaptive thinking, tool registry + human-only blacklist, parity contract test, trigger-first tool descriptions ([spec](completed/v1.8.0-chat-foundations.md), [series overview](completed/v1.8.x-agentic-chat.md)) | Completed (2026-07-09) | M |
| v1.8.1 | Chat read parity — 9 new read tools covering every human-visible query surface, strict schemas, untrusted-content labeling | Completed (2026-07-10) ([spec](completed/v1.8.1-chat-read-parity.md)) | M |
| v1.8.2 | Chat write parity — 12 new mutation tools (all two-phase confirmed), batch splits, parity contract complete | Completed (2026-07-10) ([spec](completed/v1.8.2-chat-write-parity.md)) | L |
| v1.8.3 | Agentic chat — code execution sandbox + programmatic tool calling, delegate_analysis subagent, tool search, context management, per-request effort | Completed (2026-07-10) ([spec](completed/v1.8.3-chat-agentic.md)) | L |
| v1.8.4 | Chat hardening — UserData boundary module (wrap/strip/sanitize), tool kind over SSE, multi-month finalization guard on bulk updates, validation + DRY consolidation | Completed (2026-07-15) ([spec](completed/v1.8.4-chat-hardening.md)) | S |
| v1.9.0 | Page-contextual tool routing — page signal promotes deferred tools behind a cache-invariant prefix ([spec](completed/v1.9.0-chat-tool-routing.md), [series overview](completed/v1.9.x-context-engineering.md)) | Completed (2026-07-16) | M |
| v1.9.1 | Subagent context discipline — curated hot set + deferred rest, summary re-wrapped as user_data ([spec](completed/v1.9.1-chat-subagent-discipline.md)) | Completed (2026-07-16) | S |
| v1.9.2 | Three-block system prompt — cached primer, volatile context, current-view grounding ([spec](completed/v1.9.2-chat-prompt-blocks.md)) | Completed (2026-07-16) | S |
| v1.9.3 | MCP server — registry tools for external agents with in-band two-phase confirmation ([spec](completed/v1.9.3-mcp-server.md)) | Completed (2026-07-16) | M |
| v1.9.4 | MCP + routing review hardening — token↔tool binding in the store, null-tolerant confirmation, install/identity fixes, page-signal robustness ([spec](completed/v1.9.4-mcp-review-hardening.md)) | Completed (2026-07-17) | S |

## Infrastructure Readiness

| Capability | v0.1.x | v0.2.x | v0.3.x | v0.4.x | v0.5.x | v0.6.x | v0.7.x | v0.8.x | v0.9.x | v0.10.x | v0.11.x | v1.0.x | v1.1.x | v1.2.x |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FastAPI backend | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| SQLite + aiosqlite | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | — |
| PostgreSQL 18 (Neon) + asyncpg | — | — | — | — | — | — | — | — | — | — | — | ✅ | ✅ | ✅ |
| CSV parsing | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| React frontend | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Upload flow | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Category groups | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Design system (fonts, theme) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Dark/light mode | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| App shell / navigation | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| User identity (localStorage) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | — | — |
| Reconciliation engine | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Dashboard | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Adjustment export (engine + UI) | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Budget tracking | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Month finalization | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Transaction split editing | — | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Transaction field editing + audit log | — | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Date range queries + search/filter | — | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Settlement tracking | — | — | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Settlement history (dashboard) | — | — | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Bulk transaction editing (category, tags, split) | — | — | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Orval codegen + MSW test mocks | — | — | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Spending insights + charts | — | — | — | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| YoY comparison + dark mode charts | — | — | — | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Responsive upload page (mobile) | — | — | — | — | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Drag-and-drop upload | — | — | — | — | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Upload history | — | — | — | — | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Client + server CSV validation | — | — | — | — | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Insights UX overhaul + per-person spending | — | — | — | — | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Split continuum + `household` flag (`payer_percentage` non-nullable) | — | — | — | — | — | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Spotted detection (person-name tags → 0% split) | — | — | — | — | — | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Category entity + `include_personal` budget scope | — | — | — | — | — | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Classification UI (filters, editing) | — | — | — | — | — | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Transaction exclusion | — | — | — | — | — | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Mobile app shell (bottom nav + shared component foundations) | — | — | — | — | — | — | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| Content page mobile layouts (responsive columns, form stacking, picker dialogs) | — | — | — | — | — | — | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| Settings page overhaul | — | — | — | — | — | — | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| Interaction consistency + touch targets (44px) | — | — | — | — | — | — | — | — | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| Authentication (name + password, JWT cookies) | — | — | — | — | — | — | — | — | — | — | ✅ | ✅ | ✅ | ✅ |
| Login page + session management | — | — | — | — | — | — | — | — | — | — | ✅ | ✅ | ✅ | ✅ |
| Personal budgets (per-person limits + spending computation) | — | — | — | — | — | — | — | — | — | — | ✅ | ✅ | ✅ | ✅ |
| Budget + transaction scope toggles | — | — | — | — | — | — | — | — | — | — | ✅ | ✅ | ✅ | ✅ |
| JSONB tag queries + server-side filtering | — | — | — | — | — | — | — | — | — | — | — | ✅ | ✅ | ✅ |
| Smart polling (together-session pages) | — | — | — | — | — | — | — | — | — | — | — | ✅ | ✅ | ✅ |
| SSE event bus (cross-user sync) | — | — | — | — | — | — | — | — | — | — | — | ✅ | ✅ | ✅ |
| PostgreSQL index optimization | — | — | — | — | — | — | — | — | — | — | — | ✅ | ✅ | ✅ |
| Neon pooler-aware connection handling | — | — | — | — | — | — | — | — | — | — | — | ✅ | ✅ | ✅ |
| Sequential query batching | — | — | — | — | — | — | — | — | — | — | — | ✅ | ✅ | ✅ |
| DB-backed theme preference (per-person) | — | — | — | — | — | — | — | — | — | — | — | ✅ | ✅ | ✅ |
| Password visibility toggle + confirm fields | — | — | — | — | — | — | — | — | — | — | — | ✅ | ✅ | ✅ |
| Neon sslmode → asyncpg ssl translation | — | — | — | — | — | — | — | — | — | — | — | ✅ | ✅ | ✅ |
| Structured logging (structlog + request middleware) | — | — | — | — | — | — | — | — | — | — | — | ✅ | ✅ | ✅ |
| Transaction notes (display + edit + audit trail) | — | — | — | — | — | — | — | — | — | — | — | — | ✅ | ✅ |
| "Discuss" tag elevation (icon, filter chip) | — | — | — | — | — | — | — | — | — | — | — | — | ✅ | ✅ |
| Quick-filter chips ("Has Notes", "Discuss") | — | — | — | — | — | — | — | — | — | — | — | — | ✅ | ✅ |
| Case-insensitive tags (normalize at input boundaries) | — | — | — | — | — | — | — | — | — | — | — | — | ✅ | ✅ |
| Two-dimension transaction editor (household/personal + split %) | — | — | — | — | — | — | — | — | — | — | — | — | ✅ | ✅ |
| Wider content area (`max-w-5xl`, responsive Group column) | — | — | — | — | — | — | — | — | — | — | — | — | ✅ | ✅ |
| Schema version guard (health check gate + upgrade screen) | — | — | — | — | — | — | — | — | — | — | — | — | ✅ | ✅ |
| Scoped dashboard (household/personal/all toggle) | — | — | — | — | — | — | — | — | — | — | — | — | — | ✅ |
| Budget alerts (personal scope) | — | — | — | — | — | — | — | — | — | — | — | — | — | ✅ |
| Self-documenting metric descriptions | — | — | — | — | — | — | — | — | — | — | — | — | — | ✅ |
| True household spending metric (all `household=true`, not just splits) | — | — | — | — | — | — | — | — | — | — | — | — | — | ✅ |
| Settlement transaction linking (candidate matching + Settle Up UI) | — | — | — | — | — | — | — | — | — | — | — | — | — | ✅ |

## Key Technical Decisions

- **Database**: SQLite via aiosqlite (v0.1–v0.11). PostgreSQL 18 on Neon via asyncpg (v1.0+). JSONB+GIN for tag storage. Runs locally, connects to Neon over the network.
- **Backend**: FastAPI with Clean Architecture (domain / application / infrastructure / interface)
- **Frontend**: React 19 + Tailwind v4 + Tanstack Query, Orval codegen from OpenAPI
- **Auth**: Name + password with argon2id hashing + JWT httpOnly cookies (v0.11.0). No email infrastructure, no OAuth. Password recovery via partner reset from Settings + CLI fallback. Prior to v0.11.0: no auth, two named profiles selected on upload.
- **User identity**: Post v0.11.x: JWT httpOnly cookie verified by `GET /auth/me` on load. Zustand stores `currentPersonId` in memory (no localStorage persist). Three app states: needs-setup, needs-login, authenticated. Prior to v0.11.x: localStorage via Zustand persist.
- **Information architecture**: Left sidebar with 7 pages: Dashboard / Transactions / Settle Up / Budget / Insights / Upload / Settings. "Transactions" replaces "Reconciliation" (standard finance-app naming). "Settings" absorbs person config + category management. "History" is not a standalone page — month navigation lives within Dashboard and Transactions. Finalization controls live on the Settle Up page. Insights (v0.7.0) is the together-session spending analysis page — small multiples, comparison cards, settlement trends.
- **Design system**: Satoshi font (Fontshare) + Geist Mono. Warm neutrals (not pure black/white), teal for positive, coral for negative. CSS custom properties via Tailwind v4 `@theme` for light/dark switching. Defined in `.claude/rules/web-design-system.md`.
- **Theme**: Per-person preference stored in DB (`theme_preference` on Person entity, default `"system"`). Three-way: system/light/dark. Before login: system preference only. After login: DB value applied, cached in localStorage for FOUC prevention. Tailwind v4 class strategy with `@custom-variant dark`. Synchronous `<script>` in `<head>` reads localStorage cache or falls back to `prefers-color-scheme`. Auth pages include a ThemeToggle for switching before login. Prior to v1.0.3: localStorage-only (no DB persistence).
- **App shell**: Left sidebar navigation on desktop (industry standard for finance apps). Bottom tab bar on mobile (5 primary + "More" sheet for Upload/Settings/identity). React Router v7 `createBrowserRouter` with layout routes.
- **CSV source**: Monarch Money export (Date, Merchant, Category, Account, Original Statement, Notes, Amount, Tags)
- **Transaction classification**: Two orthogonal fields — `household: bool` (is this expense part of the couple's household budget?) and `payer_percentage: int` (0-100, the payer's share — drives settlement). Settlement: any transaction where `payer_percentage < 100`. Budget: `household=true`, or category has `include_personal=true`. Neither field implies the other. There is no `TransactionType` enum — "shared", "spotted", "household-no-split" are human descriptions of field combinations, not stored types. The Monarch CSV `shared` tag maps to `household=true` with a default 50/50 split on import; "shared" is a tag name, not a domain concept.
- **Tag-to-field mapping**: `shared`/`split` tag → `household=true`, default 50/50 split. `household` tag → `household=true`, no split implied. `sXX` tag → payer pays XX% (authoritative in every combination, overrides defaults; highest wins if multiple). Person-name tag → `household=false`, 0% (spotted — the beneficiary's personal spending). No tag → `household=false`, 100% (personal). Internally stored as `payer_person_id` + `payer_percentage` + `household` on each transaction.
- **Category groups**: ~75 Monarch categories roll up into ~12 groups (e.g., "Groceries & Home Supplies" → "Food & Dining"). Budgets are set at the group level. Initial mapping seeded from JSON fixture on startup. New categories auto-created during CSV upload with `group_id=None` (unmapped). Users assign them to groups via Settings UI.
- **Adjustment export**: Pure domain functions (no stored adjustment entities). Deterministic dedup IDs via UUID5 for idempotent Monarch re-import. `couplefins-adjustment` tag for filtering.
- **Use case pattern**: Every use case has 3 objects — `Command` (frozen attrs, validated at construction), `Result` (frozen attrs), `UseCase` (`@define(slots=True)`, stateless). Uniform signature: `execute(self, command, uow) -> Result`. UoW passed to execute (not constructor). Transaction scoped via `async with uow:`. Even parameterless queries get an empty Command. Shared validators in `_shared/command_validators.py`.
- **Real-time sync**: SSE via FastAPI `EventSourceResponse` (v1.0.1+). In-memory `EventBus` broadcasts entity names after mutations; frontend `useRealtimeSync` hook connects via `EventSource` and invalidates TanStack Query caches. 5-second `refetchInterval` polling on together-session pages (Dashboard, Settle Up, Transactions) as fallback. No WebSockets, no Redis, no Neon LISTEN/NOTIFY.
- **Logging**: structlog (v1.0.4+) with `ProcessorFormatter` stdlib bridge. Console output switchable between `ConsoleRenderer` (dev) and `JSONRenderer` (prod) via `LOGGING__OUTPUT`. File sink always JSON (`logs/couplefins.log`, 10MB rotation). ASGI `RequestLoggingMiddleware` binds method/path to contextvars and logs `request_completed` with status + duration. Prior to v1.0.4: loguru with custom `_InterceptHandler`.
- **Transaction notes & discussion**: Monarch CSV `Notes` column imported since v0.1.0, stored on the Transaction entity, searchable. v1.1.0 surfaces them in the UI (icon indicator on collapsed rows, textarea in expanded editor, full audit trail). The "discuss" tag is elevated with pure UI treatment — amber `MessageCircleQuestion` icon on flagged rows, standalone quick-filter chips for "Has Notes" and "Discuss". To resolve, remove the tag via the tag editor. "Discuss" stays as a tag (not a boolean field) — it's workflow metadata, not a classification dimension.
- **Tags**: Normalized to lowercase at all input boundaries (v1.1.0): CSV parser, tag add/remove, tag update, server-side filter queries. Alembic migration `0004` lowercased existing data. Frontend `hasDiscussTag()` uses case-insensitive comparison as defense-in-depth. `DISCUSS_TAG` constant centralizes the tag name.
- **Transaction editor**: Two-dimension model (v1.1.0+): Household/Personal toggle ("Scope") + always-editable split percentage. The two fields are orthogonal — `household` controls budget inclusion, `payer_percentage` controls settlement. There is no intermediate "type" layer. Split display uses percentage format (`50%`).
- **Content layout**: Data pages use `max-w-5xl` (1024px) since v1.1.0. Settings/Account at `max-w-3xl`, auth pages at `max-w-md`. Transaction table Group column hides below `xl` (1280px viewport). Table has `pl-4`/`pr-4` on first/last columns for proper padding with expanded-row backgrounds.
- **Schema version guard**: `GET /health` returns `APP_VERSION`, `SCHEMA_VERSION` (expected Alembic head), `schema_current` (actual from `alembic_version` table), and `schema_ok` (boolean match). Frontend gates on `schema_ok` before running the auth flow. On mismatch, shows an `UpgradeScreen` distinguishing code-behind-schema (pull + restart) from schema-behind-code (restart to run migrations). Prevents cryptic SQLAlchemy errors when two laptops are at different code versions against the same Neon database.
- **Transaction edit history**: `TransactionEdit` entity tracks field-level changes (field_name, old_value, new_value, edited_at) with `edited_by_person_id` for person attribution (v1.4.0+, nullable for historical edits). Import provenance derived from `Transaction.upload_id → Upload(person_id, uploaded_at)` — no synthetic edit records for imports. `compute_edit()` shared helper in `_shared/transaction_pipeline.py` is the single creation point. Frontend timeline renders import event (from enriched API response) as the anchor, edits above. Person names resolved client-side via existing `usePersonMaps()`.
- **Tooling**: uv, Ruff, BasedPyright, pytest, Biome
