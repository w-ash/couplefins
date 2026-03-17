---
name: new-module
description: Step-by-step guide for adding a new vertical-slice module (domain → infrastructure → application → interface → tests)
argument-hint: module name (e.g., "settlement", "budget")
---

# New Module: $ARGUMENTS

Create a complete vertical slice for the `$ARGUMENTS` module. Follow each step in order.

## Step 1: Domain Entity
- Create `src/domain/$ARGUMENTS.py`
- Frozen attrs class: `@define(frozen=True, slots=True)`
- PEP 695 generics, PEP 604 unions
- Repository Protocol with batch-first methods (e.g., `save_batch`, `get_by_ids`)
- Pure parsing/validation functions — no I/O, no side effects

## Step 2: Infrastructure
- Create ORM model in `src/infrastructure/persistence/models/$ARGUMENTS.py`
- Register in `src/infrastructure/persistence/models/__init__.py` (canonical import point)
- Create repository in `src/infrastructure/persistence/repositories/$ARGUMENTS.py`
- Implement domain Protocol, include `_to_domain()` / `_to_model()` converters
- Batch variants for all write operations

## Step 3: Application (Use Case)
- Create `src/application/use_cases/$ARGUMENTS/` directory with use case modules
- Constructor injection via `UnitOfWorkProtocol`
- Use case owns transaction boundaries (commit/rollback)
- All use cases run through `execute_use_case()`

## Step 4: Interface (API Route)
- Create `src/interface/api/routes/$ARGUMENTS.py`
- Thin handlers (5-10 lines max), delegate to use cases
- Pydantic request/response models for boundary validation
- Register router in `src/interface/api/app.py`

## Step 5: Tests
Follow the test pyramid (60% unit / 35% integration / 5% E2E):

- **Domain unit tests** (`tests/unit/domain/test_$ARGUMENTS.py`): pure logic, no mocks
- **Use case unit tests** (`tests/unit/application/test_$ARGUMENTS.py`): mock UoW via `make_mock_uow()`
- **Repository integration tests** (`tests/integration/test_$ARGUMENTS_repo.py`): real DB session
- **Route integration tests** (`tests/integration/test_$ARGUMENTS_routes.py`): httpx AsyncClient
- Use factories from `tests/fixtures/factories.py` — add new ones as needed
- Cover happy path + error cases + edge cases

## Step 6: Wire Up
- Add repository to `src/application/runner.py` composition root
- Run quality gate: `uv run ruff check . --fix && uv run ruff format . && uv run basedpyright src/ && uv run pytest`
