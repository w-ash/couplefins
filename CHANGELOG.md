# Changelog

All notable changes to this project are documented here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

This project uses the `release-per-ship` mode: every shipped version gets a
dated entry here, a version bump, and a `vX.Y.Z` tag, which is what triggers a
deploy. There is no `[Unreleased]` section.

Versions before 1.14.0 predate this file. Their scope is recorded per series in
`docs/backlog/completed/` and in the version matrix in `docs/backlog/README.md`.

## [1.14.2] - 2026-09-06

### Changed

- Insights and Budget open on the latest month that has spending instead of the current calendar month, so neither page is blank until the month's CSVs are uploaded. Naming a month still wins, and naming only a year opens on that year's latest month with spending.

### Fixed

- Chat replies no longer fail on conversations containing thinking, web-search or code-sandbox steps. Prompt caching is left to the API, which skips the blocks that cannot carry a cache marker instead of the app guessing at them one production error at a time.
- The chat panel is usable again after pressing Stop. Stopping a reply left the composer disabled and every send blocked, because aborting the stream never cleared the streaming flag — the only way out was starting a new conversation.
- Insights' year-to-date now ends at the month being viewed in every year, matching its own "Jan–Mar" label, the year it compares against, and the year-to-date on Budget and the Dashboard. Viewing a past month previously showed that whole year's spending under a label naming only part of it.

## [1.14.1] - 2026-09-06

### Fixed

- Settle a catch-up payment against the net of the months it covers. A payment covering months that run in opposite directions now brings every one of them to zero, instead of clearing the oldest few and leaving the rest untouched once the money ran out.

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
