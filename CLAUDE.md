# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

Couplefins is a household finance tool for couples. Each person uses their own Monarch Money account, tags household expenses, and exports monthly CSVs. The app handles two core use cases:

1. **Settlement** — "Who owes whom?" Each transaction has a `payer_percentage` (0-100). When < 100, the difference is owed to the payer. These sum into a running outstanding balance across all months (v1.7.5); payments apply to the oldest open months first (FIFO) and are never bound to a month.
2. **Budgeting** — "Are we on track?" Each transaction has a `household` flag (bool). When true, it counts toward the household budget. Categories can also opt in personal spending via `include_personal`.

These two fields are orthogonal — a transaction can be household without being split (concert tickets each person bought), or split without being household (unusual, but the fields are independent). There is no `TransactionType` enum; "shared", "spotted", and "household-no-split" are human descriptions of field combinations, not stored types.

The Monarch CSV `shared` tag maps to `household=true` with a default 50/50 split on import. "Shared" is a tag name, not a domain concept — the domain concept is "household."

Domain details: @docs/domain.md
User goals and monthly workflow: @docs/user-flows.md
Implementation roadmap: @docs/backlog/README.md

## Core Principles (YOU MUST FOLLOW)

- **Python 3.14+** — PEP 695 generics, PEP 604 unions, PEP 649 deferred annotations, `datetime.now(UTC)`, structlog not stdlib logging, `from __future__ import annotations` is banned
- **Ruthlessly DRY** — no code duplication
- **Immutable Domain** — pure transformations, no side effects in domain layer
- **Batch-First** — design for collections, single items are degenerate cases
- **Validate at Boundaries** — typed models at entry points, trust internals

## Architecture

`Interface → Application → Domain ← Infrastructure`

- **Domain** (`src/domain/`): Pure logic, entities, repository Protocols. Zero external imports.
- **Application** (`src/application/`): Use case orchestration via `execute_use_case()`. Constructor injection.
- **Infrastructure** (`src/infrastructure/`): SQLAlchemy repos (PostgreSQL/asyncpg via Neon), CSV parsing. Implements domain Protocols.
- **Interface** (`src/interface/api/`): Thin FastAPI handlers (5-10 lines), delegates to use cases.
- **Frontend** (`web/`): React 19 + Tailwind v4 + Tanstack Query. Orval codegen from OpenAPI spec.


## Essential Commands

```bash
# Backend
uv run pytest                           # Fast tests (skips slow/diagnostic)
uv run pytest -m ""                     # All tests
uv run pytest tests/unit/ -x            # Unit tests, stop on first failure
uv run pytest -k "test_name"            # Single test by name
uv run ruff check . --fix               # Lint + autofix
uv run ruff format .                    # Format
uv run basedpyright src/                # Type check
uv run vulture                          # Dead code detection

# Frontend / full stack
pnpm dev                                # API (:8001) + Vite (:5174) together
pnpm test                               # Vitest
pnpm check                              # Biome lint + tsc + vite build
pnpm generate                           # Orval codegen (refreshes OpenAPI first)
pnpm --prefix web dev                   # Vite alone, when API isn't needed

# Quality gate (run before committing)
uv run ruff check . --fix && uv run ruff format . && uv run basedpyright src/ && uv run vulture && uv run pytest
```

## Testing Self-Check (after every implementation)

1. Did I write tests? If not, write them now.
2. Right level? Domain=unit, UseCase=unit+mocks, Repository=integration, Routes=integration.
3. Beyond happy path? Error cases, edge cases, validation.
4. Using existing factories from `tests/fixtures/`?
5. Tests pass? `uv run pytest tests/path/to/test_file.py -x`

## Planning Self-Check (before implementing a feature)

1. Which user stories in `docs/user-flows.md` does this serve?
2. What does the backlog spec in `docs/backlog/` say about implementation?
3. After implementing, do the user story's Given/When/Then criteria pass?
4. Did development reveal missing stories or stale criteria? Propose updates to `docs/user-flows.md`.
