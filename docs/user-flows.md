# User Flows

Personas, user stories, and user journeys for Couplefins.

---

## Persona

**Partner** (Alice or Bob)

Uses Monarch Money daily to track personal spending. Tags shared expenses with `shared` (and optional `sXX` split tags). Exports a CSV once a month. Primary question: "How much do I owe, or am I owed, this month?" Secondary: "Are we on budget by category?" Tech comfort is high — this is a personal dev tool. Sessions are short (~15 min) and monthly.

---

## Information Architecture

Five top-level pages in the sidebar, ordered by frequency of use:

| Page | Purpose | Ships in |
|---|---|---|
| **Dashboard** | Monthly summary at a glance, who-owes-whom, upload status, month navigation | v0.2.1 |
| **Transactions** | Shared transaction table, reconciliation summary, category breakdown, finalization | v0.2.0 |
| **Budget** | Category group budgets, monthly + YTD views, progress indicators | v0.4.0 |
| **Upload** | CSV import: select person, pick month, upload file, preview, confirm | v0.1.1 |
| **Settings** | Person config, category-to-group mappings, theme toggle | v0.1.3 (stub) |

"History" is not a standalone page — month navigation and finalization live within Dashboard and Transactions.

---

## User Stories

### Identity & Setup

**US-SETUP-1**: As a new user, I want to enter both our names so the app knows who we are.

Acceptance criteria:
- [ ] Given the app has no persons, when I open it, then I see a welcome screen with two name inputs
- [ ] Given I enter two names and submit, then both persons are created in the database
- [ ] Given I enter the same name twice, then I see a warning (but can proceed)

**US-SETUP-2**: As a new user after setup, I want to select which person I am so the app remembers me.

Acceptance criteria:
- [ ] Given setup is complete and no identity is stored, when I next see the app, then I see a profile picker with both names as large selectable cards
- [ ] Given I select my name, then my person ID is stored in localStorage
- [ ] Given I select my name, then I am redirected to the main app with navigation

**US-SETUP-3**: As a returning user, I want the app to remember me across browser sessions.

Acceptance criteria:
- [ ] Given I previously selected my identity, when I reopen the app, then I go straight to the main app without re-identifying
- [ ] Given my stored identity no longer matches a person in the database, then I see the profile picker again

**US-SWITCH-1**: As either person, I want to switch identity with one click.

Acceptance criteria:
- [ ] Given I am using the app as Alice, when I click Bob's name in the sidebar toggle, then my identity switches to Bob
- [ ] Given I switch identity, then the upload page reflects the new person
- [ ] Given I switch identity, then the change persists across page reloads

---

### Upload

**US-UPLOAD-1**: As a partner, I want to upload my Monarch CSV for a specific month so my transactions are in the system.

Acceptance criteria:
- [ ] Given I am identified, when I navigate to Upload, then my name is pre-selected as the uploader
- [ ] Given I select a CSV file and month/year, when I click Upload, then the file is parsed and transactions are stored
- [ ] Given a CSV has already been uploaded for this person + month, when I re-upload, then the previous data is replaced

**US-UPLOAD-2**: As a partner, I want to preview parsed transactions before confirming the import.

Acceptance criteria:
- [ ] Given I select a CSV, when I click Preview, then I see a table of parsed transactions
- [ ] Given the preview, then I can see which transactions are shared vs personal
- [ ] Given the preview, then I can see split percentages for shared transactions
- [ ] Given the preview, then I can go back and change my file selection

**US-UPLOAD-3**: As a partner, I want to see unmapped categories so I can fix them.

Acceptance criteria:
- [ ] Given my CSV contains categories not mapped to any group, when I preview or upload, then I see a warning listing the unmapped categories
- [ ] Given unmapped categories exist, then I can still proceed with the upload

---

### Transactions (v0.2.0)

**US-TXN-1**: As a partner, I want to see all shared transactions for a month from both of us.

Acceptance criteria:
- [ ] Given both partners have uploaded for a month, when I view Transactions, then I see a combined table of all shared transactions from both people
- [ ] Given the table, then each row shows: date, merchant, category, who paid, amount, split ratio, each person's share
- [ ] Given only one person has uploaded, then I see their transactions with a notice about the missing upload

**US-TXN-2**: As a partner, I want to see who owes whom and the net settlement amount.

Acceptance criteria:
- [ ] Given the transactions page, then I see a summary card showing "Alice owes Bob $X" or "All settled!"
- [ ] Given the summary, then I can see each person's total paid and total owed share

**US-TXN-3**: As a partner, I want to see spending broken down by category group.

Acceptance criteria:
- [ ] Given the transactions page, then I see a per-category-group breakdown table
- [ ] Given a category group row, when I expand it, then I see individual categories within that group
- [ ] Given a category has no group mapping, then it appears under "Uncategorized"

**US-TXN-4**: As a partner, I want to filter and sort transactions.

Acceptance criteria:
- [ ] Given the transaction table, then I can filter by person (Alice / Bob / both)
- [ ] Given the transaction table, then I can filter by shared / personal
- [ ] Given the transaction table, then I can sort by date, amount, or category

---

### Dashboard (v0.2.1)

**US-DASH-1**: As a returning user, I want to see the current month's status at a glance.

Acceptance criteria:
- [ ] Given I open the app, then I land on the Dashboard
- [ ] Given the dashboard, then I see the current month's net settlement ("Alice owes Bob $127.50")
- [ ] Given no uploads exist for the current month, then I see "No data yet" with a prompt to upload

**US-DASH-2**: As a partner, I want to see upload status for both people.

Acceptance criteria:
- [ ] Given the dashboard, then I see indicators for each person: uploaded or not yet
- [ ] Given one person hasn't uploaded, then I see "Waiting for [name]'s upload"

**US-DASH-3**: As a partner, I want quick actions.

Acceptance criteria:
- [ ] Given the dashboard, then I see a button to upload a CSV
- [ ] Given the dashboard, then I see a button to view the full Transactions page

**US-DASH-4**: As a partner, I want to navigate to past months.

Acceptance criteria:
- [ ] Given the dashboard, then I see a list of past months with net settlement amounts
- [ ] Given a past month, when I click it, then I navigate to the Transactions page for that month

---

### Export (v0.3.x)

**US-EXPORT-1**: As a partner, I want to download my adjustment CSV for Monarch import.

Acceptance criteria:
- [ ] Given the Transactions page, then I see a "Download Adjustments" button per person
- [ ] Given I click download, then I receive a CSV file formatted for Monarch import
- [ ] Given I have no adjustment account configured, then the button is disabled with an explanation

**US-EXPORT-2**: As a partner, I want to preview adjustments before downloading.

Acceptance criteria:
- [ ] Given the Transactions page, then I can expand a section showing adjustment rows
- [ ] Given the preview, then I see: merchant, category, amount, type (credit/debit)

---

### Settings

**US-SETTINGS-1**: As a partner, I want to configure my Monarch adjustment account name (v0.3.x).

Acceptance criteria:
- [ ] Given the Settings page, then I see a field for each person's adjustment account name
- [ ] Given I enter an account name, when I save, then it persists and is used in CSV exports

**US-SETTINGS-2**: As a partner, I want to manage category-to-group mappings.

Acceptance criteria:
- [ ] Given the Settings page, then I see a list of category groups with their mapped categories
- [ ] Given a new category appears after upload, then I can assign it to a group
- [ ] Given a mapping, then I can move a category to a different group

**US-SETTINGS-3**: As a partner, I want to select my preferred theme (v0.1.2).

Acceptance criteria:
- [ ] Given the Settings page (or a toggle in the sidebar), then I can choose: System, Light, or Dark
- [ ] Given I select a theme, then it applies immediately
- [ ] Given I selected a theme, then it persists across sessions

---

### Budget (v0.4.0)

**US-BUDGET-1**: As a partner, I want to set monthly budgets per category group.

Acceptance criteria:
- [ ] Given the Budget page, then I see a list of category groups with budget input fields
- [ ] Given I set a budget amount, when I save, then it persists with an effective_from date
- [ ] Given I change a budget mid-year, then historical months use the old amount

**US-BUDGET-2**: As a partner, I want to see spending vs budget for the current month and year-to-date.

Acceptance criteria:
- [ ] Given the Budget page, then I can toggle between Monthly and YTD views
- [ ] Given either view, then I see per-group: budget amount, actual spending, remaining, progress bar
- [ ] Given a group is under 80% of budget, then progress is green
- [ ] Given a group is 80-100% of budget, then progress is yellow
- [ ] Given a group is over budget, then progress is red

**US-BUDGET-3**: As a partner, I want to see a grand total row.

Acceptance criteria:
- [ ] Given either view, then I see a total row summing all groups

---

### History & Finalization (v0.4.1)

**US-HIST-1**: As a partner, I want to finalize a month once we agree.

Acceptance criteria:
- [ ] Given the Transactions page for a month, then I see a "Finalize" button
- [ ] Given I finalize, then the month is locked and marked with a finalized indicator
- [ ] Given a finalized month, then uploads for that month are rejected

**US-HIST-2**: As a partner, I want to browse past months from the Dashboard.

Acceptance criteria:
- [ ] Given the Dashboard, then I see a history section with past months
- [ ] Given a past month row, then I see: month, total shared spending, net settlement, finalized status
- [ ] Given a past month, when I click it, then I see the full Transactions view for that month

**US-HIST-3**: As a partner, I want to prevent accidental changes to finalized months.

Acceptance criteria:
- [ ] Given a finalized month, when I try to upload a CSV for that month, then I see an error
- [ ] Given a finalized month, then I can optionally un-finalize with confirmation

---

## User Journeys

### Journey 1: First-Time Setup

| Step | Screen | Action | Result |
|---|---|---|---|
| 1 | Welcome (full-screen) | Open app for the first time | See welcome screen with two name inputs |
| 2 | Welcome | Enter "Alice" and "Bob", click Get Started | Both persons created in database |
| 3 | Profile Picker (full-screen) | See two large cards: "Alice" and "Bob" | — |
| 4 | Profile Picker | Click "Alice" | Identity stored in localStorage via Zustand |
| 5 | Upload (in app shell) | Redirected to Upload page | Sidebar visible, "Alice" shown as current user |

### Journey 2: Returning Monthly Upload

| Step | Screen | Action | Result |
|---|---|---|---|
| 1 | Dashboard (or Upload) | Open app | Recognized from localStorage, land on default page |
| 2 | — | See sidebar | Current user (Alice) shown with toggle to Bob |
| 3 | Upload | Navigate to Upload | Person pre-filled as Alice |
| 4 | Upload | Select February 2026, choose CSV file | — |
| 5 | Upload (preview) | Click Preview | See parsed transactions table |
| 6 | Upload (confirmed) | Click Confirm Import | Transactions saved, success summary shown |
| 7 | Transactions | Navigate to Transactions | See February data (if Bob also uploaded) |

### Journey 3: User Switching

| Step | Screen | Action | Result |
|---|---|---|---|
| 1 | Any page | See sidebar: "[Alice] Bob" toggle | Alice is active (emphasized) |
| 2 | Sidebar | Click "Bob" | Identity switches to Bob |
| 3 | Any page | Page reflects Bob's context | Upload defaults to Bob, localStorage updated |

### Journey 4: Monthly Reconciliation

| Step | Screen | Action | Result |
|---|---|---|---|
| 1 | Dashboard | See "Both uploaded for February" | — |
| 2 | Transactions | Navigate to Transactions | See combined shared transaction table |
| 3 | Transactions | View summary card | "Alice owes Bob $127.50" |
| 4 | Transactions | Expand category group | See per-category breakdown |
| 5 | Transactions (v0.3.x) | Click "Download Adjustments" | CSV downloaded for Monarch import |
| 6 | Transactions (v0.4.x) | Click "Finalize February" | Month locked, finalized indicator shown |

### Journey 5: Budget Review

| Step | Screen | Action | Result |
|---|---|---|---|
| 1 | Budget | Navigate to Budget | See category groups with budget vs actual |
| 2 | Budget | Toggle to YTD view | See cumulative Jan–current month |
| 3 | Budget | See "Food & Dining" at 92% | Yellow progress bar |
| 4 | Budget | See "Travel" at 150% | Red progress bar, over budget |

### Journey 6: Settings & Configuration

| Step | Screen | Action | Result |
|---|---|---|---|
| 1 | Settings | Navigate to Settings | See sections: Theme, Categories, People |
| 2 | Settings | Toggle theme to Dark | App switches to dark mode immediately |
| 3 | Settings | See "Unmapped: Coffee Shops & Treats" | New category from recent upload |
| 4 | Settings | Assign to "Food & Dining" group | Mapping saved |
| 5 | Settings (v0.3.x) | Set adjustment account: "Shared Adjustments" | Saved, enables export |
