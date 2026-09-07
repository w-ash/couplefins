# Changelog

All notable changes to this project are documented here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

This project uses the `release-per-ship` mode: every shipped version gets a
dated entry here, a version bump, and a `vX.Y.Z` tag, which is what triggers a
deploy. There is no `[Unreleased]` section.

Versions before 1.14.0 predate this file. Their scope is recorded per series in
`docs/backlog/completed/` and in the version matrix in `docs/backlog/README.md`.

## [1.14.0] - 2026-09-06

### Added

- Serve the app at a URL instead of only on each laptop, hosted on Fly.io.
- Serve the built frontend from the API's own origin, so one process is the whole app.
- Add `/api/v1/health/live`, a database-free probe for the hosting platform's health check.
- Make the rotating log file opt-in via `LOGGING__FILE_PATH`; unset means stdout only.
- Seed a fresh database with Monarch's default category groups, so a new environment starts with a usable taxonomy. A gitignored `data/category_groups.json` still takes precedence where one exists.

### Fixed

- Target the configured database when running `alembic` from the command line, instead of always localhost.
- Resolve the migrations directory absolutely, so migrations run from any working directory.
