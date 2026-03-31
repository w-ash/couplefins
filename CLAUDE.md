# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

Couplefins is a shared finance reconciliation tool for couples. Each person uses their own Monarch Money account, tags shared expenses, and exports monthly CSVs. This app replaces their spreadsheet for reconciling who owes whom and tracking shared budgets by category.

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

# Frontend
pnpm --prefix web dev                       # Vite dev server (port 5173)
pnpm --prefix web test                      # Vitest
pnpm --prefix web check                     # Biome lint + tsc
pnpm --prefix web generate                  # Orval codegen

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
