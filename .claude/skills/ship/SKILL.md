---
name: ship
description: Ship a completed backlog version — reconcile work against stories, update backlog & roadmap, bump version, run quality gate, and commit.
argument-hint: version (e.g., "v1.2.2") — omit to auto-detect next Planned version
user_invocable: true
disable-model-invocation: true
allowed-tools: Bash Read Edit Grep Glob
---

# Ship $ARGUMENTS

Post-implementation release workflow for a completed backlog version.

Recent commit conventions:
!`git log --oneline -5`

## Step 0: Pre-flight

- Run `git status` to see the current state. If there are unexpected untracked or modified files beyond implementation work, warn the user before proceeding.
- Read `docs/backlog/README.md` and find the target version:
  - If `$ARGUMENTS` is a version number, use it directly.
  - If `$ARGUMENTS` is empty, find the first `Planned` row in the Version Matrix — that's the version being shipped.
- Read the corresponding `docs/backlog/vX.Y.x.md` file.
- Read `pyproject.toml` to check the current version.
- If all stories in the target version are already `[x]` AND the README row already says `Completed`, stop and report: "This version is already shipped."

## Step 1: Reconcile implementation against backlog

- Review `git diff` (staged + unstaged) and `git status` to understand what was actually implemented.
- Compare the actual changes against each unchecked `- [ ]` story in the target version:
  - **Clearly done**: The implementation fully satisfies the story's "What" — check it off.
  - **Partially done or done differently**: Update the story's Notes to describe what actually shipped and how it differs. Check it off only if the intent was met, even if the approach changed.
  - **Not touched**: Leave unchecked.
- If implementation substantially deviates from the plan (new scope, skipped stories, different architecture), stop and report the discrepancies. Wait for instructions.

## Step 2: Update the backlog stories

In `docs/backlog/vX.Y.x.md`, for each story confirmed as done:
- Check the box: `- [ ]` → `- [x]`
- Set `Status: Completed (YYYY-MM-DD)` with today's date
- Add or update the `What:` field to describe what actually shipped (not just what was planned)
- Update Notes if the implementation differed from the original plan

## Step 3: Update the roadmap

In `docs/backlog/README.md`:
- If **all** stories in the target version are now `[x]`, update the Version Matrix row from `Planned` to `Completed (YYYY-MM-DD)`.
- If unchecked stories remain, update the row to `Partial` and leave the version open.

## Step 3b: Archive completed version file

If **all** stories across the **entire** `vX.Y.x.md` file (every sub-version, not just the one being shipped) are now `[x]`:
- `git mv docs/backlog/vX.Y.x.md docs/backlog/completed/vX.Y.x.md`
- Create `docs/backlog/completed/` if it doesn't exist yet.
- This only triggers when the whole minor series is done (e.g., all of v1.2.0–v1.2.2), not just one sub-version within it.

## Step 4: Check user-flows.md

Read `docs/user-flows.md` and check the planning self-check:
- Did development reveal missing stories or stale acceptance criteria?
- Are there Given/When/Then criteria that no longer match what shipped?
- If updates are needed, propose them to the user — don't silently edit user-flows.md.

## Step 5: Bump the version

Compare the completed version number against `version` in `pyproject.toml`:
- If the completed version is **higher** → bump `pyproject.toml` to match.
- If equal or lower → skip (the project has already moved past this version).

Also update `src/config/constants.py`:
- `APP_VERSION` must match `pyproject.toml` version.
- `SCHEMA_VERSION` must match the current Alembic head. Check with `ls alembic/versions/` — the highest-numbered migration is the head. If a new migration was added in this version, update `SCHEMA_VERSION` to match.

## Step 6: Sync lockfile

Run `uv sync` to update `uv.lock` — but only if Step 5 changed `pyproject.toml`. Otherwise skip.

## Step 7: Code health — zero tolerance

Zero warnings, zero errors, zero test failures. Nothing is "pre-existing" — if it shows up, fix it now. Every warning is a design improvement opportunity.

Run each gate. If anything fails, fix it before moving on. If a fix would be a significant refactor (5+ files, public API change), present options to the user instead of silently choosing.

**Vulture**: When vulture flags unused code, determine whether it's a **false positive** (framework-consumed field, Pydantic serialization, test utility) or **genuinely dead code**. If dead → **delete it**. If false positive → add to `vulture_whitelist.py` with an explanation. Never whitelist real dead code — that defeats the purpose of the tool.

```bash
# Backend
uv run ruff check . --fix && uv run ruff format .
uv run basedpyright src/            # 0 errors AND 0 warnings required
uv run vulture
uv run pytest

# Frontend
pnpm --prefix web generate          # Orval codegen (required if backend schemas changed)
pnpm --prefix web check             # Biome + tsc + build
pnpm --prefix web test
```

Do not proceed to commit until every gate is clean.

## Step 8: Stage and commit

- List the files that will be staged (backlog files, pyproject.toml, uv.lock if changed, plus any unstaged implementation files).
- Stage files by explicit name — never `git add -A` or `git add .`.
- Commit following the conventions from the git log. Format: `Add vX.Y.Z: concise summary of what shipped`.
- Include the `Co-Authored-By` trailer.
- If the commit fails due to a pre-commit hook, fix and re-stage. Do NOT use `--no-verify`.
