# Couplefins

Shared finance reconciliation tool for couples. Each person uses their own Monarch Money account, tags shared expenses, and exports monthly CSVs. Couplefins replaces the spreadsheet for reconciling who owes whom and tracking shared budgets by category.

## The Problem

Two people share expenses but track finances separately in Monarch Money. Each month they need to figure out who owes whom, check budget progress, and settle up. The spreadsheet they used was manual, error-prone, and nobody looked forward to updating it.

## The Solution

Each person exports their Monarch CSV, uploads it, and reviews their shared transactions. Then they sit down together for ~15 minutes to settle the balance, review the budget, and lock the month. The app handles the math, tracks history, and exports adjustment CSVs back to Monarch so each person's account reflects their true share.

## Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) for dependency management
- Node.js 22+ and [pnpm](https://pnpm.io/) for the web UI
- PostgreSQL 18 — either a [Neon](https://neon.tech) account (recommended) or a local install

## Database Setup

The app uses PostgreSQL via SQLAlchemy async (asyncpg). You need a running PostgreSQL instance — either remote on Neon or local on your machine.

### Option A: Neon (recommended)

1. Create a free project at [neon.tech](https://neon.tech)
2. Copy the connection string from the Neon dashboard
3. Set it in `.env`:
   ```
   DATABASE__URL=postgresql+asyncpg://user:pass@ep-xxxx.us-east-2.aws.neon.tech/couplefins?sslmode=require
   ```

Neon handles connection pooling, backups, and branching. The app connects over the network — no local database files.

### Option B: Local PostgreSQL

1. Install PostgreSQL 18 (`brew install postgresql@18` on macOS)
2. Create a database:
   ```bash
   createdb couplefins
   ```
3. Set it in `.env`:
   ```
   DATABASE__URL=postgresql+asyncpg://localhost:5432/couplefins
   ```

### Running migrations

After setting `DATABASE__URL`, create the schema:

```bash
uv run alembic upgrade head
```

### Test database

Integration tests use the same `DATABASE__URL` from your environment. Unit tests don't need a database. To run integration tests:

```bash
uv run pytest tests/integration/ -x    # Requires DATABASE__URL
uv run pytest tests/unit/ -x           # No database needed
```

## Quick Start

```bash
# Clone and install
git clone https://github.com/w-ash/couplefins.git
cd couplefins
uv sync

# Set up environment
cp .env.example .env
# Edit .env with your DATABASE__URL (see Database Setup above)

# Run database migrations
uv run alembic upgrade head

# Install frontend dependencies
pnpm --prefix web install

# Start both servers (API on 8001, UI on 5174)
pnpm --prefix web start
```

## Development

```bash
# Backend
uv run pytest                           # Fast tests (skips slow/diagnostic)
uv run pytest -m ""                     # All tests
uv run pytest tests/unit/ -x            # Unit tests, stop on first failure
uv run ruff check . --fix               # Lint + autofix
uv run ruff format .                    # Format
uv run basedpyright src/                # Type check

# Frontend
pnpm --prefix web dev                   # Vite dev server (port 5174)
pnpm --prefix web test                  # Vitest
pnpm --prefix web check                 # Biome lint + tsc
pnpm --prefix web generate             # Orval codegen from OpenAPI spec

# Quality gate (run before committing)
uv run ruff check . --fix && uv run ruff format . && uv run basedpyright src/ && uv run pytest
pnpm --prefix web check && pnpm --prefix web test
```

## Project Structure

```
src/
├── domain/          # Pure business logic, entities, repository protocols
├── application/     # Use case orchestration (Command/Result/UseCase pattern)
├── infrastructure/  # SQLAlchemy repos (PostgreSQL/asyncpg), CSV parsing
├── interface/       # FastAPI route handlers
└── config/          # Settings, constants, logging

web/src/
├── api/             # Fetch client, query client, generated hooks
├── components/      # Shared UI components
├── layouts/         # App shell, sidebar
├── lib/             # Utilities, formatting, constants
├── pages/           # Route-level page components
├── stores/          # Zustand stores (identity, theme)
└── test/            # Test setup, utilities, providers

tests/
├── unit/            # Domain + use case tests (mocked)
├── integration/     # Repository + API route tests (real DB)
└── fixtures/        # Factory functions, mock UoW
```

## Documentation

- [Domain concepts](docs/domain.md) — Monarch Money conventions, reconciliation math, accounting model
- [User flows](docs/user-flows.md) — Personas, monthly workflow, user stories with acceptance criteria
- [Project roadmap](docs/backlog/README.md) — Version matrix, infrastructure readiness, technical decisions
