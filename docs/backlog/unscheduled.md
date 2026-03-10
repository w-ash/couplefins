# Unscheduled Backlog

Ideas and features without version assignment. Move to a version file when ready to commit.

## Data & Import
- Automatic CSV format detection (support non-Monarch CSVs)
- Drag-and-drop upload with file validation preview
- Duplicate transaction detection across uploads
- Transaction editing after upload (fix miscategorized items)
- Manual split entry UI (enter split percentages directly instead of relying on Monarch tags)
- Unmapped category alerts (notify when uploaded transactions contain categories not in any group)

## Reconciliation
- Settlement tracking (mark debts as paid, record payment date)
- Export reconciliation summary as PDF
- Email/notification when both uploads are in for a month
- Split ratio defaults per category group (auto-apply a default split when no sXX tag is present, e.g., rent is always 60/40)

## Budgets
- Budget vs. actual trend charts over time
- Rollover unused budget to next month
- Budget alerts when approaching limit mid-month

## UI & UX
- Dark/light theme toggle
- Mobile-responsive layout
- Keyboard shortcuts for common actions
- Data visualization (spending trends, category pie charts)

## Infrastructure
- PostgreSQL migration path for remote deployment
- User authentication (if sharing with others)
- Automated backups of SQLite database
- Docker containerization
