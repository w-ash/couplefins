# Unscheduled Backlog

Ideas and features without version assignment. Move to a version file when ready to commit.

## Data & Import
- Automatic CSV format detection (support non-Monarch CSVs)

## Reconciliation
- Export reconciliation summary as PDF
- Email/notification when both uploads are in for a month

## Budgets
- Rollover unused budget to next month
- Budget alerts when approaching limit mid-month
- Pace line (daily cumulative spend vs ideal rate through current month) — Copilot Money's most praised pattern, but requires daily granularity within a month (different data shape from the year-overview sparklines in v0.7.x). Could be a dashboard sparkline or an Insights page detail view.

## Together Session & Communication
- Monthly recap card at finalization — fun stats: top merchant, biggest category swing, biggest single transaction, streak of months under budget
- Milestones / streaks — "6 months tracking", "3 months under budget on Food & Dining", "$X,XXX settled total"

## Recurring & Smart Detection
- Recurring expense detection — same merchant + similar amount across months → surface as a "Subscriptions" view
- ~~Natural language spending queries via Claude API~~ → moved to v1.5.x (Chat Assistant)

## Chat Assistant
- Memory tool / cross-session persistence — needs storage + person-scoping design. Security note for that design: persistent memory is a prompt-injection reinfection vector (Anthropic containment write-up, May 2026) — plan startup-phase scanning of persisted state.

## UI & UX
- Keyboard shortcuts for common actions
- PWA manifest + service worker — installable on mobile, push notification for "time to export your CSV" on the 1st

## Infrastructure
- Rethink cold start — what should a fresh database actually get? v1.14.0 made
  a fresh database bootable by committing a generic default taxonomy, with the
  household's own as a gitignored override. That fixed the blocker but left the
  shape unexamined: seeding still happens at every boot behind a row count, the
  two fixtures can drift, and a new household gets 77 categories it never chose
  rather than being asked. Worth considering: seed on first setup instead of at
  boot, let the first CSV upload propose the taxonomy, or make the default
  editable in Settings before any data lands.
