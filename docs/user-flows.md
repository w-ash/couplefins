# User Flows

What the couple is trying to accomplish with Couplefins, and what success looks like.

For enforcement rules, see [`.claude/rules/web-design-system.md`](../.claude/rules/web-design-system.md). For design rationale, see [`ui-identity.md`](ui-identity.md). For data model and accounting concepts, see [`domain.md`](domain.md).

---

## Persona

**Partner** (Alice or Bob)

Uses Monarch Money daily to track personal spending. Tags shared expenses with `shared` (and optional `sXX` split tags). Exports a CSV once a month. Tech comfort is high — this is a personal dev tool built by one of them.

Each person uses their own laptop. Identity is set once during setup and rarely changed — Alice is always Alice on Alice's machine. The sidebar toggle exists for edge cases (showing your partner something on your screen), not daily switching.

**Primary question**: "How much do I owe, or am I owed?"
**Secondary**: "Are we on budget?" and "How's this year going overall?"

---

## The Monthly Ritual

Everything in the app supports a monthly cycle with two phases:

### Solo prep (days before the together session)

Each person, on their own time:

1. Exports their Monarch CSV for the month
2. Uploads it to Couplefins
3. Reviews shared transactions — fixes miscategorized items, corrects split percentages, bulk-edits tags
4. Checks for unmapped categories and assigns them to groups

**Success**: Both uploads are in, data looks right. Ready for the together session.

### Together session (~15 minutes, side by side on separate laptops)

The couple sits down to:

1. Open the dashboard — see who owes whom, whether anything needs attention
2. Settle up — record the payment (Venmo, cash, etc.)
3. Review budget — are we on track this month? This year?
4. Finalize the month — lock it so nothing shifts
5. (Optional) Export adjustment CSVs to import back into Monarch for accurate personal spending

**Success**: Settlement is paid, budget is reviewed, month is locked. The whole thing took fifteen minutes.

---

## Information Architecture

Seven top-level pages in the sidebar, ordered by workflow:

| Page | Purpose | Ships in |
|---|---|---|
| **Dashboard** | "Now" view — settlement status, upload readiness, YTD overview, month history. Each card owns its own temporal context. | v0.2.1 |
| **Transactions** | Shared transaction table with search, filtering, bulk editing, category breakdown | v0.2.0 |
| **Settle Up** | Record payments, waive balances, link settlement transactions, finalization controls | v0.6.0 |
| **Budget** | Category group budgets, monthly + YTD views, progress indicators, spending charts | v0.4.0 |
| **Insights** | Spending trend sparklines per category group, comparison cards, budget overlays, settlement balance trend, YoY comparison | v0.7.0 |
| **Upload** | CSV import: preview, confirm, re-upload. Drag-and-drop in v0.8.x | v0.1.1 |
| **Settings** | Person config, category-to-group mappings, adjustment accounts, theme | v0.1.3 |

The Dashboard has no date picker — it's a "now" view where each card owns its own temporal context (settlement shows the active month, stats show year-to-date, history shows trends). Other pages have their own date selectors as needed.

---

## User Stories

### Getting Started

One-time setup. The couple does this once and never thinks about it again.

**US-SETUP-1**: As a new user, I want to enter both our names so the app knows who we are.

- Given the app has no persons, when I open it, then I see a welcome screen with two name inputs
- Given I enter two names and submit, then both persons are created
- Given I enter the same name twice, then I see a warning (but can proceed)

**US-SETUP-2**: As a new user, I want to select which person I am so the app remembers me on this device.

- Given setup is complete, then I see a profile picker with both names as large selectable cards
- Given I select my name, then I'm redirected to the main app and my identity persists across sessions
- Given my stored identity no longer matches the database, then I see the picker again

---

### Importing Data

Getting transaction data into the system. Each person does this solo, on their own time.

**Goal**: My Monarch CSV is in Couplefins, correctly parsed, with no surprises.

**US-IMPORT-1**: As a partner, I want to upload my Monarch CSV so my shared transactions are in the system.

- Given I navigate to Upload, then my name is pre-selected as the uploader
- Given I select a CSV file, when I click Upload, then the file is parsed and transactions are stored
- Given a CSV has already been uploaded for this person + month, when I re-upload, then the previous data is replaced

**US-IMPORT-2**: As a partner, I want to preview what will be imported before committing.

- Given I select a CSV, then I see a table of parsed transactions: which are shared vs personal, split percentages, and counts (new, changed, unchanged)
- Given the preview, then I can go back and change my file selection

**US-IMPORT-3**: As a partner, I want to know about unmapped categories so I can fix them before or after importing.

- Given my CSV contains categories not mapped to any group, then I see a warning listing them
- Given unmapped categories, then I can still proceed with the upload (fixing in Settings later)

**US-IMPORT-4** (v0.8.x): As a partner, I want to drag-and-drop my CSV and see my upload history.

- Given the Upload page, then I can drag a file onto a drop zone instead of using a file picker
- Given I've uploaded before, then I see a history of past uploads with dates and transaction counts

---

### Reviewing & Correcting Transactions

Making sure the data is right before settling. This is solo prep work — each person reviews their own transactions and fixes mistakes.

**Goal**: Shared transactions are correctly categorized, correctly split, and correctly tagged. I'm confident the settlement amount will be accurate.

**US-REVIEW-1**: As a partner, I want to see all shared transactions for a period from both of us.

- Given both partners have uploaded, then I see a combined table of all shared transactions from both people
- Given each row, then I see: date, merchant, category, who paid, amount, split ratio, each person's share
- Given only one person has uploaded, then I see their transactions with a notice about the missing upload

**US-REVIEW-2**: As a partner, I want to find specific transactions quickly.

- Given the transaction table, then I can search by merchant name or text
- Given the transaction table, then I can filter by person, by shared/personal, or by date range
- Given the transaction table, then I can sort by date, amount, or category

**US-REVIEW-3**: As a partner, I want to fix mistakes — wrong category, wrong split, wrong tag — without re-uploading.

- Given a transaction, then I can edit its category, date, amount, split percentage, or tags
- Given multiple transactions with the same problem, then I can select them and bulk-edit in one action
- Given any edit, then an audit trail records what changed, when, and the previous value

**US-REVIEW-4**: As a partner, I want to see spending broken down by category group.

- Given the transactions page, then I see a per-category-group breakdown
- Given a category group, when I expand it, then I see individual categories and their totals
- Given an unmapped category, then it appears under "Uncategorized"

**US-REVIEW-5** (v0.9.x): As a partner, I want to exclude a specific transaction from reconciliation without deleting it.

- Given a transaction, then I can toggle it to "excluded" so it doesn't count toward settlement
- Given an excluded transaction, then it's visually distinct and can be re-included

---

### Understanding Where We Stand

The dashboard is the landing page. It answers "what's going on and what do I need to do?" — differently depending on whether you're in solo prep or sitting down together.

**Goal**: In ten seconds, I know the state of our shared finances and where to go next.

**US-DASH-1**: As a partner opening the app, I want to immediately understand the current state of our shared finances.

- Given I open the app, then I land on the Dashboard
- Given we have transaction data, then I see who owes whom for the most recent active month and year-to-date summary stats
- Given no transaction data exists, then I see a directional empty state prompting me to upload

**US-DASH-2**: As a partner doing solo prep, I want to know what I need to do before our together session.

- Given the dashboard, then I see whether each person has uploaded for the active month
- Given I haven't uploaded yet, then I can navigate directly to Upload
- Given there are unmapped categories, then I see a warning so I can fix them in Settings

**US-DASH-3**: As a partner sitting down together, I want to get to the right action quickly — settle up, review budget, or finalize.

- Given there's an outstanding balance, then the settlement card links directly to Settle Up
- Given the dashboard, then I can navigate to Transactions or Settle Up in one click

**US-DASH-4**: As a partner, I want to see how recent months have gone so I can spot trends and catch unfinished business.

- Given the dashboard, then I see a month history showing spending, settlement status, and finalization state for each month with data
- Given an unfinalized month, then I can tell at a glance it needs attention
- Given a month row, when I click it, then I navigate to the Transactions page for that month

---

### Settling Up

Recording who paid whom. This is the core "together moment" — the reason the couple sits down side by side.

**Goal**: The balance is paid, recorded, and both people agree on the number.

**US-SETTLE-1**: As a partner, I want to see exactly who owes whom and record a payment.

- Given the Settle Up page, then I see a hero card with the current month's settlement amount ("Alice owes Bob $147.50")
- Given I enter an amount and payment method (Venmo, cash, etc.), when I click Record Payment, then the payment is recorded and the remaining balance updates

**US-SETTLE-2**: As a partner, I want to waive a small balance instead of transferring money.

- Given a small outstanding balance, then I can waive it (forgive the debt) with a note
- Given a waived balance, then the month shows as settled

**US-SETTLE-3**: As a partner, I want to link a bank transaction to the settlement so it doesn't count as a shared expense.

- Given a Venmo transfer appears in my uploaded transactions, then I can mark it as a settlement transaction
- Given a linked settlement transaction, then it's excluded from reconciliation math

**US-SETTLE-4**: As a partner, I want to see all past payments for this month.

- Given the Settle Up page, then I see a history of recorded payments with amounts, methods, and dates
- Given a mistake, then I can undo a recorded payment

---

### Tracking the Budget

Are we on track for the month and the year? The couple reviews this together.

**Goal**: We know which category groups are over budget and can adjust our spending before it gets worse.

**US-BUDGET-1**: As a partner, I want to set monthly budgets per category group.

- Given the Budget page, then I see category groups with budget input fields
- Given I set a budget amount, when I save, then it persists with an effective date
- Given I change a budget mid-year, then historical months use the old amount

**US-BUDGET-2**: As a partner, I want to see spending vs budget for the current month and year-to-date.

- Given the Budget page, then I can toggle between Monthly and YTD views
- Given either view, then I see per-group: budget amount, actual spending, remaining, and a health indicator
- Given a group approaching or over budget, then the indicator communicates urgency without alarm (teal → amber → coral)

**US-BUDGET-3**: As a partner, I want to see a grand total so I know our overall position.

- Given either view, then I see a total row summing all groups

**US-BUDGET-4** (v0.7.x): As a partner, I want to see spending trends over time so we can have data-driven conversations.

- Given the Budget or a dedicated Insights page, then I see line/area charts of monthly spending per category group across the year
- Given a chart, then I can toggle category groups on/off to focus on specific areas
- Given a chart, then I can see budget limit lines overlaid to spot when we crossed thresholds
- Given a year-over-year mode, then I can compare this year's spending trajectory to last year's

---

### Closing the Month

Finalization and export happen together at the end of the together session. Once a month is closed, it shouldn't shift.

**Goal**: The month is locked, both Monarch accounts are updated, and we can move on.

**US-CLOSE-1**: As a partner, I want to finalize a month once we agree the numbers are right.

- Given the Settle Up page for a month, then I see a "Lock Month" button
- Given I finalize, then the month is locked — uploads and edits for that month are rejected
- Given a finalized month, then I can un-finalize with confirmation if we discover a mistake

**US-CLOSE-2**: As a partner, I want to export adjustment CSVs so each person's Monarch account reflects their true share.

- Given the Transactions page, then I see a "Download Adjustments" button per person
- Given I click download, then I receive a CSV formatted for Monarch import
- Given I want to check first, then I can preview the adjustment rows before downloading
- Given I have no adjustment account configured, then the button is disabled with an explanation

---

### Configuring the App

Setup and maintenance tasks that happen occasionally, not monthly.

**US-CONFIG-1**: As a partner, I want to manage category-to-group mappings so new Monarch categories get assigned correctly.

- Given the Settings page, then I see category groups with their mapped categories
- Given a new category appears after upload, then I can assign it to a group
- Given an existing mapping, then I can move a category to a different group

**US-CONFIG-2**: As a partner, I want to configure my Monarch adjustment account name for CSV export.

- Given the Settings page, then I see a field for each person's adjustment account name
- Given I enter an account name, when I save, then it persists and is used in CSV exports

**US-CONFIG-3**: As a partner, I want to select my preferred theme.

- Given the Settings page (or sidebar toggle), then I can choose: System, Light, or Dark
- Given I select a theme, then it applies immediately and persists across sessions

---

## User Journeys

### Journey 1: First-Time Setup

| Step | Screen | Action | Result |
|---|---|---|---|
| 1 | Welcome | Open app for the first time | Welcome screen with two name inputs |
| 2 | Welcome | Enter "Alice" and "Bob", click Get Started | Both persons created |
| 3 | Profile Picker | See two large cards | — |
| 4 | Profile Picker | Click "Alice" | Identity stored, redirected to Upload |

### Journey 2: Solo Prep (Monthly Upload + Review)

| Step | Screen | Action | Result |
|---|---|---|---|
| 1 | Dashboard | Open app days before together session | See upload status — Alice hasn't uploaded for March yet |
| 2 | Upload | Navigate to Upload, select March CSV | Preview shows 47 transactions, 23 shared |
| 3 | Upload | Click Confirm Import | Transactions saved, success summary |
| 4 | Transactions | Navigate to Transactions for March | See shared transactions; notice "Uber Eats" is miscategorized |
| 5 | Transactions | Select 3 Uber Eats transactions, bulk-edit category to "Food Delivery" | All three updated, audit trail recorded |
| 6 | Dashboard | Return to Dashboard | Upload status shows Alice uploaded; Bob hasn't yet |

### Journey 3: Together Session (Settle + Budget + Finalize)

| Step | Screen | Action | Result |
|---|---|---|---|
| 1 | Dashboard | Both open app together in April | Settlement card: "March 2026: Alice owes Bob $147.50", both uploaded |
| 2 | Dashboard | Click "Settle Up →" | Navigate to Settle Up page |
| 3 | Settle Up | See hero card: "Alice owes Bob $147.50" | Upload statuses confirmed, payment history visible |
| 4 | Settle Up | Enter $147.50, select Venmo, click Record Payment | "Payment recorded" — remaining balance $0.00 |
| 5 | Budget | Navigate to Budget, toggle to YTD | Food & Dining at 92% (amber), Travel at 40% (teal) |
| 6 | Budget | Discuss — agree to eat out less next month | — |
| 7 | Settle Up | Return to Settle Up, click Lock Month | March finalized, lock indicator appears |
| 8 | Dashboard | Return to Dashboard | March shows locked in history; dashboard surfaces next unfinalized month |

### Journey 4: Budget Review

| Step | Screen | Action | Result |
|---|---|---|---|
| 1 | Budget | Navigate to Budget | Category groups with budget vs actual for current month |
| 2 | Budget | Toggle to YTD | Cumulative Jan–current month |
| 3 | Budget | See "Food & Dining" at 92% | Amber indicator — approaching limit |
| 4 | Budget | See "Travel" at 150% | Coral indicator — over budget |
| 5 | Budget (v0.7.x) | View spending chart | Monthly trend lines per category group across the year |

### Journey 5: Settings & Configuration

| Step | Screen | Action | Result |
|---|---|---|---|
| 1 | Settings | Navigate to Settings | Sections: Theme, Categories, People |
| 2 | Settings | Toggle theme to Dark | App switches immediately |
| 3 | Settings | See "Unmapped: Coffee Shops & Treats" | New category from recent upload |
| 4 | Settings | Assign to "Food & Dining" group | Mapping saved |
| 5 | Settings | Set adjustment account: "Shared Adjustments" | Enables export on Transactions page |
