# Completed Versions

Index of shipped versions. When all stories in a version file are done, move the file here.

| Version | Shipped | Summary |
|---|---|---|
| v0.1.0 | 2026-03-09 | Project scaffold, data model, CSV parser, category groups |
| v0.1.1 | 2026-03-10 | Upload flow (API + UI), frontend scaffold, person management |
| v0.1.2 | 2026-03-10 | Design foundations: Satoshi/Geist Mono fonts, warm theme, dark/light mode |
| v0.1.3 | 2026-03-10 | App shell, sidebar navigation, Zustand identity store, profile picker |
| v0.1.4 | 2026-03-10 | UI audit & polish across all pages and components |
| v0.1.5 | 2026-03-10 | Use case architecture refactor: uniform Command/Result/UseCase pattern, UoW context manager |
| v0.2.0 | 2026-03-10 | Reconciliation engine, transactions page, dedup-aware uploads, month selector |
| v0.2.1 | 2026-03-10 | Nullable category mappings, auto-create categories from CSV, category management UI |
| v0.2.2 | 2026-03-11 | Dashboard landing page, YTD reconciliation, month history, Button component, UploadPage refactor |
| v0.3.0 | 2026-03-11 | Adjustment export engine (per-person Monarch-importable CSVs) |
| v0.3.1 | 2026-03-11 | Export UI (download adjustments from transactions page) |
| v0.4.0 | 2026-03-12 | Budget tracking (monthly + YTD, set budgets, view progress) |
| v0.4.1 | 2026-03-12 | Month finalization (lock months, prevent changes) |
| v0.5.0 | 2026-03-12 | Transaction split editing (individual + bulk) |
| v0.5.1 | 2026-03-12 | Transaction field editing + audit log |
| v0.5.2 | 2026-03-13 | Solo prep polish, settlement card hero & category icons |
| v0.5.3 | 2026-03-13 | Plain language & verb+object CTAs |
| v0.5.4 | 2026-03-13 | Guardrails: empty, loading, error states |
| v0.5.5 | 2026-03-13 | Transaction search, filtering & date range |
| v0.6.0 | 2026-03-15 | Settlement page, recording & bulk editing |
| v0.6.1 | 2026-03-16 | Settlement history (Dashboard enrichment) |
| v0.6.2 | 2026-03-16 | Code quality cleanup (DRY, consistency) |
| v0.6.3 | 2026-03-16 | DRY enforcement & month navigation |
| v0.6.4 | 2026-03-16 | Orval codegen activation + MSW test infrastructure |
| v0.7.0 | 2026-03-17 | Spending trends — small multiples charts + Insights page |
| v0.7.1 | 2026-03-17 | Comparison cards, budget lines & settlement balance trend |
| v0.7.2 | 2026-03-17 | Year-over-year overlay, dark mode charts & drill-down |
| v0.8.0 | 2026-03-17 | Responsive upload layout (mobile + desktop) |
| v0.8.1 | 2026-03-17 | Drag-and-drop file zone |
| v0.8.2 | 2026-03-17 | Upload history (endpoint + UI) |
| v0.8.3 | 2026-03-18 | CSV validation & error quality (client + server) |
| v0.8.4 | 2026-03-18 | Confirmation & flow polish |
| v0.8.5 | 2026-03-18 | Insights page UX overhaul — controls, KPI hierarchy, "Who's paying" |
| v0.9.0 | 2026-03-18 | Split continuum + household flag + spotted detection |
| v0.9.1 | 2026-03-18 | Category entity + include_personal budget scope |
| v0.9.2 | 2026-03-18 | Classification UI: filters, type editing, preview polish |
| v0.9.3 | 2026-03-18 | Transaction exclusion flag |
| v0.10.0 | 2026-03-19 | App shell + shared component mobile foundations |
| v0.10.1 | 2026-03-20 | Content pages mobile layouts (Dashboard, Transactions, Settle Up) |
| v0.10.2 | 2026-03-20 | Settings page overhaul (desktop + mobile quality) |
| v0.10.3 | 2026-03-21 | Interaction consistency + touch polish |
| v0.11.0 | 2026-03-24 | Auth backend (name+password, JWT cookies, protected routes) |
| v0.11.1 | 2026-03-25 | Auth frontend (login page, setup flow, session management) |
| v0.11.2 | 2026-03-26 | Personal budget backend (per-person limits, spending computation) |
| v0.11.3 | 2026-03-26 | Scope UI (budget toggle, transaction scope filter) |
| v1.0.0 | 2026-03-27 | PostgreSQL migration — Neon, asyncpg, JSONB+GIN, data migration |
| v1.0.1 | 2026-03-28 | Multi-user readiness — smart polling, SSE event bus, index audit |
| v1.0.2 | 2026-03-28 | Query optimization — Neon pool tuning, query batching, tag filtering |
| v1.0.3 | 2026-03-28 | DRY audit, DB-backed theme preference, auth UX, sslmode fix |
| v1.0.4 | 2026-03-30 | Structured logging — loguru → structlog, request middleware, JSON logs |
| v1.1.0 | 2026-03-31 | Notes, discuss elevation, case-insensitive tags, editor & layout polish |
| v1.1.1 | 2026-03-31 | Schema version guard — health endpoint versioning, upgrade screen |
| v1.2.0 | 2026-04-01 | Scoped dashboard — household/personal/all toggle, budget alerts, self-documenting metrics |
| v1.2.1 | 2026-04-01 | Terminology cleanup — "shared" → "household" throughout codebase, remove `TransactionType` |
| v1.2.2 | 2026-04-03 | Settlement transaction linking — candidate matching, Settle Up linking UI |
| v1.2.3 | 2026-04-03 | Brand identity — CoupleFins logo, favicon, Lucide v1 upgrade, lighter strokes |
| v1.2.4 | 2026-04-04 | Transaction-first settlement flow — link transactions instead of recording payments |
| v1.3.0 | 2026-04-04 | Per-month budget model — replace cascading effective dates with year/month |
| v1.3.1 | 2026-04-06 | Copy from last month + budget page UX polish |
| v1.3.2 | 2026-04-07 | Budget trends on Insights page — budget overlay lines on spending charts |
| v1.3.3 | 2026-04-05 | Accounting guardrails — rounding fix, zero-sum assertion, settlement link validation, pre-finalization warnings |
| v1.3.4 | 2026-04-06 | Monetary type consistency, budget/adjustment invariants, settlement amount validation |
| v1.3.5 | 2026-04-06 | Graceful degradation, zero-tolerance type safety, error handling split |
| v1.4.0 | 2026-04-07 | Edit attribution — `edited_by_person_id` on TransactionEdit, threaded through all edit use cases |
| v1.4.1 | 2026-04-08 | Import provenance — enriched edit history endpoint with upload-derived import event |
| v1.4.2 | 2026-04-08 | Transaction history timeline — vertical timeline UI with import anchor + person-attributed edits |
| v1.5.0 | 2026-04-10 | Chat assistant — right-edge panel, read-only queries via Claude API, mobile full-screen page, suggested questions |
| v1.5.1 | 2026-04-10 | Chat UX polish — streaming markdown, tool-call result cards |
| v1.5.2 | 2026-04-10 | Chat mutations — budget updates, transaction edits with confirmation cards |
| v1.5.3 | 2026-04-10 | Chat hardening — architecture layering fix, integration tests, rate limiting, input safety |
| v1.5.4 | 2026-04-10 | Chatbot voice — composable voice system, Fiona character, per-user voice setting |
| v1.5.5 | 2026-04-12 | Chat UX affordances — new conversation, copy message, regenerate last reply, friendly limit error |
| v1.6.0 | 2026-05-02 | Settle Up audit table + Transactions buckets — payer-split ledger, narrative, spotted scope, header cards |
| v1.6.1 | 2026-07-02 | Audit table & header-card correctness — settled-state honesty, one sign convention, link anchors, drill-through fidelity |
| v1.7.0 | 2026-07-03 | Settlement correctness — waiver fix, settlement scope, sXX precedence, finalization guards |
| v1.7.1 | 2026-07-03 | Upload & re-upload integrity — true replace, flag preservation, dedup window, parser hardening |
| v1.7.2 | 2026-07-03 | Budget & dashboard math — sign-aware spending, YTD totals, unmapped visibility, copy-budgets gate |
| v1.7.3 | 2026-07-03 | Insights & chat accuracy — comparison cards, settled trend, YTD cutoff, chat scope & local dates |
| v1.7.4 | 2026-07-03 | Guardrails & DRY — shared exclusion predicate, suppression removal, fixture realism |
| v1.7.5 | 2026-07-04 | Settlement ledger — running outstanding balance, multi-month catch-ups, derived FIFO month status |
| v1.8.0 | 2026-07-09 | Agentic chat foundations — Opus 4.8 + adaptive thinking, tool registry + human-only blacklist, parity contract test |
| v1.8.1 | 2026-07-10 | Chat read parity — 9 new read tools covering every human-visible query surface, untrusted-content labeling |
| v1.8.2 | 2026-07-10 | Chat write parity — 12 new mutation tools (all two-phase confirmed), batch splits, parity contract complete |
| v1.8.3 | 2026-07-10 | Agentic chat — code execution sandbox + programmatic tool calling, delegate_analysis subagent, tool search, context management, per-request effort |
| v1.8.4 | 2026-07-15 | Chat hardening — UserData boundary module (wrap/strip/sanitize), tool kind over SSE, multi-month finalization guard, validation + DRY consolidation |
| v1.9.0 | 2026-07-16 | Page-contextual tool routing — page signal promotes deferred tools behind a cache-invariant prefix/tail split |
| v1.9.1 | 2026-07-16 | Subagent context discipline — curated hot set + deferred rest behind tool search, summary marked UserData |
| v1.9.2 | 2026-07-16 | Three-block system prompt — cached primer, volatile context block, current-view page grounding |
| v1.9.3 | 2026-07-16 | MCP server — registry read/write tools over stdio with in-band two-phase confirmation, args-drift rejection |
