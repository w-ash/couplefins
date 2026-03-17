---
name: plan-feature
description: Ground a feature in user-flows.md and backlog before planning, validate after implementation. Use when starting work on a backlog version or new feature.
argument-hint: version (e.g., "v0.7.0") or feature name (e.g., "spending trends")
---

# Plan Feature: $ARGUMENTS

Ground this feature in the existing behavioral spec before designing or implementing.

## Step 1: Load Context
- Read `docs/user-flows.md` — identify which user stories relate to `$ARGUMENTS`
- Read `docs/backlog/README.md` — find the version this maps to
- Read the relevant `docs/backlog/v0.X.x.md` — understand the implementation spec
- If `$ARGUMENTS` is a version number, use it directly. If it's a feature name, search the backlog README version matrix for the matching version.

## Step 2: Identify User Stories
List the specific user stories from user-flows.md that this feature satisfies. If no existing story covers this feature, note that — a new story will be needed in Step 5.

## Step 3: Cross-Reference
- Does the backlog spec cover everything the user stories require?
- Are there acceptance criteria in user-flows.md that the backlog doesn't address?
- Are there backlog tasks that go beyond what user-flows.md describes?
- Flag any misalignments.

## Step 4: Plan Implementation
With both documents as context, design the implementation. Follow the `new-module` skill for new vertical slices, or plan incrementally for extensions to existing modules.

## Step 5: Spec Evolution (if needed)
If planning revealed gaps, propose specific changes:
- **New user stories**: Draft in Given/When/Then format, placed in the relevant workflow section with version annotation
- **Updated criteria**: Show old vs. new acceptance criteria
- **Version annotation changes**: If a story's scope shifted to a different version

Present proposals inline — the user decides whether to apply them.

## Step 6: Post-Implementation Validation
After implementing, walk through each relevant user story's Given/When/Then criteria:
- For each criterion, confirm the implementation satisfies it (with file paths or test names as evidence)
- Flag any criteria not yet satisfied and note what remains
