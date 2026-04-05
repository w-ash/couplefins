---
name: review
description: Multi-agent review — spawns scoped reviewers in parallel, collects structured reports, synthesizes a unified verdict.
argument-hint: scope (e.g., "plan", "branch:feature-x", "pr:123", file paths) — omit to review uncommitted changes
user_invocable: true
disable-model-invocation: true
allowed-tools: Bash Read Grep Glob
---

# Review $ARGUMENTS

Spawn scoped reviewers in parallel, collect their structured reports, and synthesize a unified verdict.

## Step 0: Determine Scope and Mode

### Detect review mode

Two modes — tell every reviewer which one applies:

**Plan review** — when `$ARGUMENTS` contains "plan", points to a backlog/design doc, or when the changed files are exclusively in `docs/`:
- Reviewers assess the *proposal*, not running code.
- Source of truth: `docs/user-flows.md`, `docs/domain.md`, `docs/backlog/`.

**Code review** — everything else (uncommitted changes, branch diff, PR, specific files):
- Reviewers assess the *implementation*.

### Detect scope

1. If `$ARGUMENTS` is "plan" → review the next planned version's backlog file (find the first `Not started` row in `docs/backlog/README.md`, read that `docs/backlog/vX.Y.x.md`).
2. If `$ARGUMENTS` specifies a branch → `git diff main...$ARGUMENTS`
3. If `$ARGUMENTS` specifies a PR → use `gh pr diff`
4. If `$ARGUMENTS` specifies file paths → use those files directly
5. If `$ARGUMENTS` is empty, auto-detect:
   - Feature branch → `git diff main...HEAD`
   - Main with staged changes → `git diff --cached`
   - Main with unstaged changes → `git diff`
   - Main with no changes → `git diff HEAD~1`

Run `git diff --stat` (or read the doc) to get a summary of changed files. Store this list — you need it for Step 1.

**For plan mode**: Read the plan file content now. You will embed it directly into each reviewer's prompt so no reviewer wastes a turn reading it.

## Step 1: Select Reviewers by Changed Paths

Examine the changed file paths and select only the relevant reviewers:

| Changed paths | Reviewers |
|---|---|
| `src/**/*.py` (backend source) | architecture-guardian, security-reviewer, test-pyramid-architect, domain-reviewer |
| `web/src/**` (frontend source) | frontend-reviewer, security-reviewer |
| `docs/**` (documentation) | domain-reviewer |
| `tests/**` (test files) | test-pyramid-architect |
| Config/infra files (pyproject.toml, alembic/, .github/) | architecture-guardian, security-reviewer |
| **Plan mode** (regardless of paths) | **all 5 reviewers** |
| **No match / fallback** | **all 5 reviewers** |

If files match multiple patterns, union the reviewer sets. Deduplicate.

## Step 2: Build Prompts and Dispatch

For each selected reviewer, construct a spawn prompt using this template:

```
**Mode**: [Plan review / Code review]
**Scope**: [summary of what changed or which doc to review]
**Changed files relevant to your domain**:
[filtered list — only files this reviewer should care about]

[FOR PLAN MODE ONLY — embed the full plan content between markers:]
---
[full plan file content]
---
All context you need is provided above. You may use Grep for ONE quick spot-check if needed, but do NOT use Read to open source files. Evaluate the PLAN against your rules, then write your report.

[FOR CODE MODE ONLY:]
[git diff --stat summary]
Read the changed files relevant to your domain, then write your report.
```

**Spawn all selected reviewers in parallel as background Agent calls in a single message.** Each reviewer runs independently — no cross-messaging, no team creation.

Use `subagent_type` matching the agent name (e.g., `architecture-guardian`, `frontend-reviewer`).

## Step 3: Synthesize

After ALL reviewers complete, collect their reports and produce a unified review.

### Aggregation rules

**Verdict**: Any REJECTED = overall REJECTED. Any APPROVED WITH SUGGESTIONS (but no rejections) = APPROVED WITH SUGGESTIONS. All APPROVED = APPROVED.

**Deduplication**: If multiple reviewers cite the same file and line, merge into one entry noting which reviewers flagged it.

**Sorting**: Violations first, then Suggestions, then Observations.

### Output format

```markdown
# Review Report
**Mode**: [Plan / Code] | **Scope**: [what was reviewed] | **Reviewers**: [list who ran]

## Verdict: [APPROVED | APPROVED WITH SUGGESTIONS | REJECTED]

## Violations (must fix)
[Merged and deduplicated violations from all reviewers. Cite which reviewer(s) flagged each.]

## Suggestions (should fix)
[Merged suggestions, grouped by theme]

## Observations
[Cross-cutting patterns, praise, systemic concerns]

## Per-Reviewer Summary
| Reviewer | Verdict | Top Finding |
|---|---|---|
| Architecture | ... | ... |
| Security | ... | ... |
| ... | ... | ... |
```

If a reviewer failed to produce a report (hit maxTurns without output despite the stop hook), note this in the summary: "Reviewer X did not produce a report."
