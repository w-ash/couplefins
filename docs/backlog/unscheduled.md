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
- Natural language spending queries via Claude API — "How much did we spend on dining last 3 months?" (single input on Dashboard or Insights)

## UI & UX
- Keyboard shortcuts for common actions
- PWA manifest + service worker — installable on mobile, push notification for "time to export your CSV" on the 1st

## Infrastructure
- Docker containerization (if deploying beyond local laptops)
