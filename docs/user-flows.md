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
2. Settle up — link the settlement transactions (Venmo, Zelle, etc.)
3. Review budget — are we on track this month? This year?
4. Finalize the month — lock it so nothing shifts
5. (Optional) Export adjustment CSVs to import back into Monarch for accurate personal spending

**Success**: Settlement is paid, budget is reviewed, month is locked. The whole thing took fifteen minutes.

---

## Information Architecture

Seven top-level pages in the sidebar, ordered by workflow, plus a chat assistant panel:

| Page | Purpose | Ships in |
|---|---|---|
| **Dashboard** | "Now" view — settlement status, upload readiness, YTD overview, month history. Each card owns its own temporal context. | v0.2.1 |
| **Transactions** | Shared transaction table with search, filtering, bulk editing, category breakdown | v0.2.0 |
| **Settle Up** | Link settlement transactions, waive balances, finalization controls | v0.6.0 |
| **Budget** | Category group budgets, monthly + YTD views, progress indicators, spending charts | v0.4.0 |
| **Insights** | Spending trend sparklines per category group, comparison cards, budget overlays, settlement balance trend, YoY comparison | v0.7.0 |
| **Upload** | CSV import: preview, confirm, re-upload. Drag-and-drop in v0.8.x | v0.1.1 |
| **Settings** | Person config, category-to-group mappings, adjustment accounts, theme | v0.1.3 |
| **Ask** *(panel)* | Chat assistant — natural language queries about spending, budgets, settlements. Right-edge panel on desktop, full-screen page on mobile. Optional (requires API key). | v1.5.0 |

The Dashboard has no date picker — it's a "now" view where each card owns its own temporal context (settlement shows the active month, stats show year-to-date, history shows trends). Other pages have their own date selectors as needed.

The Ask panel is not a sidebar navigation item — it lives in a separate right-edge tab on desktop because the left sidebar's mental model is "navigate to a page." The chat panel opens alongside the current page without navigating away. On mobile, it's a full-screen page in the "More" menu.

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

- Given I select a CSV, then I see a table of parsed transactions: classification (personal, shared, spotted, household), split percentages, and counts (new, changed, unchanged)
- Given transactions tagged with my partner's name, then the preview shows them as "spotted" with the beneficiary identified
- Given transactions tagged `household`, then the preview shows them as "household" with no split
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

**Goal**: Transactions are correctly classified (personal, shared, spotted, household), correctly split, and correctly tagged. I'm confident the settlement amount and budget totals will be accurate.

**US-REVIEW-1**: As a partner, I want to see all household transactions for a period from both of us.

- Given both partners have uploaded, then I see a combined table of all household transactions from both people — shared, spotted, and household (no split)
- Given each row, then I see: date, merchant, category, who paid, amount, split ratio, each person's share, and classification type
- Given only one person has uploaded, then I see their transactions with a notice about the missing upload

**US-REVIEW-2**: As a partner, I want to find specific transactions quickly.

- Given the transaction table, then I can search by merchant name or text
- Given the transaction table, then I can filter by person, by classification type (shared, spotted, household), or by date range
- Given the transaction table, then I can sort by date, amount, or category

**US-REVIEW-3**: As a partner, I want to fix mistakes — wrong category, wrong split, wrong tag — without re-uploading.

- Given a transaction, then I can edit its category, date, amount, split percentage, or tags
- Given multiple transactions with the same problem, then I can select them and bulk-edit in one action
- Given any edit, then an audit trail records what changed, when, and the previous value

**US-REVIEW-4**: As a partner, I want to see spending broken down by category group.

- Given the transactions page, then I see a per-category-group breakdown
- Given a category group, when I expand it, then I see individual categories and their totals
- Given an unmapped category, then it appears under "Uncategorized"

**US-REVIEW-5** (v0.9.x): As a partner, I want to see transaction classifications correctly after upload.

- Given my CSV contains transactions tagged with my partner's name, then they appear as "spotted" with my partner identified as the beneficiary
- Given a spotted transaction, then I see it marked as 100% owed back to me — it enters settlement but is not a shared budget expense (it's a debt)
- Given my CSV contains transactions tagged `household`, then they appear as "household" — they count toward the shared budget but don't generate a settlement entry
- Given my CSV contains transactions tagged `shared`, then they enter both settlement (split) and budget

**US-REVIEW-6** (v0.9.x): As a partner, I want to change a transaction's classification after upload.

- Given a transaction, then I can change its type between personal, shared, spotted, and household in the expanded row editor
- Given I change a transaction to spotted, then it enters settlement at 100% reimbursement
- Given I change a transaction to household, then it counts toward the budget but not settlement
- Given I change a transaction to personal, then it exits both settlement and budget (unless the category has `include_personal`)
- Given any classification change, then an audit trail records what changed

**US-REVIEW-7** (v0.9.x): As a partner, I want to filter transactions by classification type.

- Given the transaction table, then I can filter by type: All / Shared / Spotted / Household / Personal
- Given the spotted filter, then I see only transactions I fronted for my partner (or they fronted for me)
- Given the household filter, then I see transactions relevant to the couple but not split — shared experiences paid individually

**US-REVIEW-8** (v0.9.x): As a partner, I want to exclude a specific transaction from reconciliation without deleting it.

- Given a transaction, then I can toggle it to "excluded" so it doesn't count toward settlement or budget
- Given an excluded transaction, then it's visually distinct and can be re-included

**US-REVIEW-9** (v1.1.x): As a partner, I want to see and edit transaction notes so I can add context during solo prep.

- Given a transaction with notes imported from Monarch, then I see a `StickyNote` icon in the collapsed row indicating notes exist
- Given I expand the transaction, then I see the notes in a textarea and can edit them
- Given I edit a note and save, then the change is tracked in the audit trail like any other field edit
- Given the transaction table, then I can filter to "Has Notes" via a quick-filter chip to see only annotated transactions

**US-REVIEW-10** (v1.1.x): As a partner, I want to flag transactions for discussion so my partner sees them during our together session.

- Given a transaction I want to discuss, then I can add a "discuss" tag (via the existing tag editor)
- Given a transaction tagged "discuss", then I see a prominent `MessageCircleQuestion` icon in the collapsed row — more eye-catching than the notes icon
- Given the transaction table, then I can filter to "Discuss" via a quick-filter chip that shows a count badge of flagged transactions
- Given I expand a flagged transaction, then I see a "Mark Discussed" button that removes the tag in one click
- Given I mark a transaction as discussed, then the icon disappears and the discuss count decrements

**US-REVIEW-11** (v1.4.x): As a partner, I want to see the full lifecycle of a transaction — when it was imported and by whom, plus any field changes — so I can trust the data during our together session.

- Given I expand a transaction that has never been edited, then I see "Imported by {name} on {date}" as the only history entry
- Given I expand a transaction that has been edited, then I see the import event at the bottom and edits above it, each showing who changed what and when
- Given an edit was made before v1.4.0 (no person tracking), then I see the edit with date and change details but no person name
- Given a transaction whose CSV was re-uploaded, then the import event shows the date of the most recent upload, not the original

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

Linking bank transactions to show that the balance has been paid. The payment itself happens outside the app (Venmo, Zelle, cash). Both sides of the transfer appear in each person's uploaded CSV. The couple identifies the matching transactions and marks them as the settlement.

**Goal**: The balance is settled, both people agree on the number, and the transfer transactions are excluded from spending.

**US-SETTLE-1**: As a partner, I want to see who owes whom and link matching bank transactions as the settlement.

- Given the Settle Up page, then I see a hero card with the current month's settlement amount ("Alice owes Bob $147.50")
- Given both partners have uploaded, then I see matching transfer pairs (e.g., Venmo debit + credit) sorted by amount
- Given I select a matching pair, when I click "Mark as settlement", then both transactions are linked, excluded from spending, and the remaining balance updates
- Given the app has configurable settlement merchants (Venmo, Zelle, etc. — set in Settings), then candidates are scored by merchant match, amount match, and category
- Given I tag a transaction `settlement` in Monarch before export, then it is automatically excluded on import

**US-SETTLE-2**: As a partner, I want to waive a small balance instead of transferring money.

- Given a small outstanding balance, then I can waive it (forgive the debt) with a note
- Given a waived balance, then the month shows as settled

**US-SETTLE-3**: As a partner, I want to link transactions to an existing settlement after the fact.

- Given a settlement in payment history without linked transactions, then I can open a link dialog and select matching transfers
- Given a linked transaction, then it appears beneath its settlement in payment history

**US-SETTLE-4**: As a partner, I want to see all past settlements for this month.

- Given the Settle Up page, then I see a history of linked settlements and waivers with amounts and dates
- Given a mistake, then I can delete a settlement (which unlinks the transactions)

---

### Tracking the Budget

Are we on track for the month and the year? The couple reviews this together.

**Goal**: We know which category groups are over budget and can adjust our spending before it gets worse.

**US-BUDGET-1**: As a partner, I want to set monthly budgets per category group.

- Given the Budget page for a month, then I see category groups with budget amounts (or empty if none set)
- Given I set a budget amount for a group, when I save, then it persists for that specific month
- Given I change a budget for one month, then other months are unaffected
- Given I delete a budget for a group, then it's removed for this month only

**US-BUDGET-2**: As a partner, I want to see spending vs budget for the current month and year-to-date.

- Given the Budget page, then I can toggle between Monthly and YTD views
- Given either view, then I see per-group: budget amount, actual spending, and a health indicator
- Given a group approaching or over budget, then the indicator communicates urgency without alarm (teal → amber → coral)
- Given YTD view, then the YTD budget is the sum of individual monthly budgets (not a cascading amount)
- Given a month with no budget set, then that month contributes $0 to the YTD budget total
- Given YTD view and a group is budgeted in some months but not others, then I see an informational note like "3 of 4 months budgeted" — a fact, not a warning

**US-BUDGET-3**: As a partner, I want to see a grand total so I know our overall position.

- Given either view, then I see a total row summing all groups

**US-BUDGET-4** (v0.9.x): As a partner, I want certain categories to include personal spending so we see total spending across both of us.

- Given the Settings page (category management), then I can toggle "Include personal spending" per category
- Given a category with personal spending included, then its budget totals reflect all transactions — household and personal
- Given a category without the toggle, then only household transactions count (tagged `shared`, `household`, or person-name)
- Given the toggle, then settlement math is unaffected — only budget reporting changes

**US-BUDGET-5** (v0.7.x): As a partner, I want to see spending trends over time so we can have data-driven conversations.

- Given the Budget or a dedicated Insights page, then I see line/area charts of monthly spending per category group across the year
- Given a chart, then I can toggle category groups on/off to focus on specific areas
- Given a chart, then I can see budget limit lines overlaid to spot when we crossed thresholds
- Given a year-over-year mode, then I can compare this year's spending trajectory to last year's

**US-BUDGET-6** (v1.3.x): As a partner, I want to copy budgets from a previous month so I don't re-enter them every month.

- Given I open the Budget page for a month with no budgets, and a previous month has budgets, then I see a "Copy budgets from [source month]" card — the source is the most recent month with budgets, not necessarily the immediately previous month
- Given I click copy, then all household budgets plus my personal budgets from the source month are created for this month (my partner's personal budgets are theirs to copy)
- Given I've already set some budgets for this month, then only missing groups are copied (no overwrites)
- Given no previous month has any budgets, then I see the "Add your first budget" empty state instead
- Given the copy succeeds, then the budgets appear immediately — the transition from empty to populated IS the feedback
- Given the copy fails (network error), then I see an error message and the empty state remains unchanged

**US-BUDGET-7** (v1.3.x): As a partner, I want household and personal budgets to be completely separate views.

- Given I toggle to "Household" scope, then I see only household budgets — personal budgets are not visible
- Given I toggle to "My Budget" scope, then I see only my personal budgets — household budgets are not visible
- Given a category group has `include_personal` categories, then the household budget's spending and average hint include personal transactions, with a "(incl. personal)" indicator so I set the target appropriately

**US-BUDGET-8** (v1.3.x): As a partner, I want to see budget lines on spending trend charts.

- Given the Insights page spending trends, then I see a dashed line showing the budget amount per month overlaid on each group's spending chart
- Given my budget changed between months, then the overlay reflects the actual budget for each month
- Given a group with no budget, then no overlay line is shown

**US-BUDGET-9** (v1.3.x): As a partner, I want the empty-month Budget page to give me useful context while I decide what to do.

- Given a month with no budgets, then the scope toggle and month picker remain usable (no full-page blocker)
- Given a month with spending but no budgets, then I see unbudgeted group spending below the copy card (US-BUDGET-6) — context for setting amounts
- Given the budget overview is still loading, then I see a skeleton (not a premature empty state that flickers into a copy card)

**US-BUDGET-10** (v1.3.x): As a partner reviewing a past month, I want to set up next month's budgets while I'm already here.

- Given I'm viewing a past month's budget (e.g., March in April), and the next month has no budgets, then I see a subtle prompt near the month picker: "Set up [next month] budgets?"
- Given I click the prompt, then the month picker advances to the next month, showing the empty-month experience (copy card or add-first-budget)
- Given the next month already has budgets, then no prompt is shown

---

### Closing the Month

Finalization and export happen together at the end of the together session. Once a month is closed, it shouldn't shift.

**Goal**: The month is locked, both Monarch accounts are updated, and we can move on.

**US-CLOSE-1**: As a partner, I want to finalize a month once we agree the numbers are right.

- Given the Settle Up page for a month, then I see a "Lock Month" button
- Given missing uploads, unsettled balance, or unmapped categories, then I see inline warnings on the finalization banner — advisory, not blocking (v1.3.3)
- Given all pre-finalization checks pass, then no warnings are shown
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

**US-CONFIG-4** (v1.2.2): As a partner, I want to configure which merchants we use for settlement payments so the app can find matching transactions.

- Given the Settings page, then I see a "Settlement merchants" section with configured merchants (seeded with Venmo, Zelle, Cash App)
- Given I add a merchant (name + pattern), then it appears in the list and is used for candidate matching on the Settle Up page
- Given I delete a merchant, then it's no longer used for matching
- Given I record a settlement, then the method dropdown is populated from configured merchants (plus "Other" as a freeform fallback)

---

### Asking Questions (v1.5.x)

A natural language assistant for quick answers without page-hopping. Optional — the app works identically without it.

**Goal**: Get instant answers to spending, budget, and settlement questions during solo prep or the together session.

**US-CHAT-1** (v1.5.x): As a partner, I want to ask spending questions in plain language and get answers from our data.

- Given the chat panel is open, when I type "How much did we spend on dining in March?", then the assistant queries our transaction data and responds with the total, broken down by category if relevant
- Given I ask "Who owes whom for March?", then the assistant returns the settlement balance for that month
- Given I ask a question about a month with no data, then the assistant tells me no transactions exist for that period
- Given I ask an ambiguous question ("How's the budget?"), then the assistant asks a clarifying follow-up or assumes the current month and states its assumption

**US-CHAT-2** (v1.5.x): As a partner, I want the chat panel accessible from any page without losing my place.

- Given any page in the app on desktop, then I see a small icon tab on the right edge of the viewport
- Given I click the icon tab (or press ⌘K), then a chat panel expands from the right and the page content compresses to make room
- Given the panel is open, then I can still interact with the page content (scrolling, clicking links) — the content is narrower but fully functional
- Given I close the panel (click close button, press Escape, or press ⌘K again), then the content expands back and my conversation is preserved until I navigate away or refresh
- Given the API key is not configured, then the icon tab does not render

**US-CHAT-3** (v1.5.x): As a partner, I want the assistant to know who I am and what month it is without me having to say so.

- Given I'm logged in as Alice and ask "What do I owe?", then the assistant checks settlement for the current active month from Alice's perspective
- Given I ask "Are we over budget?", then the assistant checks household budgets for the current month
- Given I ask about "last month", then the assistant resolves it relative to the current date

**US-CHAT-4** (v1.5.x): As a partner, I want to see the assistant's progress when it's looking things up.

- Given the assistant needs to query data, then I see a brief indicator ("Looking up March spending...")
- Given the response is streaming, then I see text appear progressively (not all at once after a delay)
- Given a tool call fails, then I see a clear error message and can retry my question

**US-CHAT-5** (v1.5.x): As a partner, I want the assistant's responses to be well-formatted — not a wall of text.

- Given the assistant returns a spending breakdown, then I see it as a compact table or list (not a paragraph of numbers)
- Given the assistant references a specific transaction, then I see merchant, amount, date, and category inline
- Given the assistant returns a budget summary, then I see group names with spent/budget amounts and health indicators matching the Budget page's visual language

**US-CHAT-6** (v1.5.x): As a partner on mobile, I want to ask questions without the chat blocking the whole app.

- Given I'm on a mobile viewport, then the "More" menu includes an "Ask" item (alongside Upload and Settings)
- Given I tap "Ask", then I navigate to a full-screen chat page with a back button
- Given I'm in the chat page, then the experience is identical to the desktop panel — same messages, same streaming, same tool indicators
- Given I press back, then I return to the page I was on (conversation is lost on navigation, same as desktop)

**US-CHAT-7** (v1.5.x): As a partner, I want to see example questions so I know what to ask.

- Given I open the chat panel (or page) with no prior messages, then I see 3-4 suggested questions as tappable chips
- Given the suggestions are context-aware: if there's an outstanding balance, one chip is "Who owes whom?"; if budgets are set, one is "Are we on budget?"
- Given I tap a suggestion, then it populates the input and sends immediately

**US-CHAT-8** (v1.5.x): As a partner, I want to update budgets through the chat with a confirmation step.

- Given I say "Set the Food & Dining budget to $700 for April", then the assistant shows a confirmation card: "Set Food & Dining to $700.00 for April 2026? [Confirm] [Cancel]"
- Given I click Confirm, then the budget is updated and the assistant confirms the change
- Given I click Cancel, then nothing changes and the assistant acknowledges the cancellation
- Given the month is finalized, then the assistant tells me the month is locked and I need to unfinalize first

**US-CHAT-9** (v1.5.x): As a partner, I want to edit transaction splits through the chat with a confirmation step.

- Given I say "Change the Whole Foods transaction from March 15 to 70/30", then the assistant finds the matching transaction and shows a confirmation card with transaction details and the proposed split change
- Given multiple transactions match, then the assistant lists them and asks me to clarify which one
- Given I confirm, then the split is updated and the audit trail records the change

**US-CHAT-10** (v1.5.x): As a partner, I want to tag transactions through the chat.

- Given I say "Tag all the Uber Eats transactions from March as household", then the assistant shows a confirmation card listing the affected transactions and the proposed change
- Given I confirm, then the transactions are updated (household flag set, audit trail recorded)
- Given the count is large (>10), then the assistant confirms the count before showing the full confirmation

**US-CHAT-11** (v1.5.x): As a partner, I want the chat assistant to have personality so it feels like talking to a person, not a robot.

- Given I open the chat panel, when the assistant responds, then the tone matches the configured voice — not a generic AI assistant
- Given I ask about spending, then the assistant frames numbers conversationally using the voice's vocabulary and style
- Given I ask about budgets, then the assistant uses plain language and gives actionable reads, not dry summaries

**US-CHAT-12** (v1.5.x): As a partner, I want to choose between chat personalities so I can pick the tone I prefer.

- Given the Account page, then I see a "Chat personality" selector alongside the theme toggle
- Given I select "Fiona" (default), then chat responses use Fiona's warm Southern CPA voice
- Given I select "Standard", then chat responses use a neutral, minimal-personality tone
- Given I change my voice, then my next chat message uses the new voice (no page refresh needed — the system prompt rebuilds per request)

**US-CHAT-13** (v1.5.x): As a partner, I want to start a new conversation so I can ask an unrelated question without earlier context biasing the assistant.

- Given the chat panel has messages, then I see a "New conversation" control in the controls row above the input
- Given I click "New conversation", then the message list clears immediately and the suggested questions reappear
- Given no messages exist, then the control is hidden (nothing to clear)

**US-CHAT-14** (v1.5.x): As a partner, I want to copy the assistant's reply so I can paste a figure into Monarch or a message.

- Given a completed assistant reply, when I hover the bubble (desktop) or view it on mobile, then I see a Copy icon
- Given I click Copy, then the reply's markdown is on my clipboard and the icon briefly changes to a check with "Copied" tooltip
- Given a reply is still streaming, then Copy is disabled on that bubble until completion

**US-CHAT-15** (v1.5.x): As a partner, I want to regenerate the assistant's last reply so I can try again when it missed the question or a tool failed.

- Given the last message is a completed assistant reply, then I see a Regenerate control in the controls row above the input
- Given I click Regenerate, then the last reply is removed and a new reply streams in its place (replace-in-place — no version toggle)
- Given streaming is in progress, then Regenerate is disabled
- Given the last reply errored, then Regenerate is still available

**US-CHAT-16** (v1.5.x): As a partner hitting the conversation length limit, I want a clear message telling me what to do next.

- Given I send a message and the conversation exceeds the backend cap (50 messages), then I see an inline error: "This conversation is full. Start a new one to continue."
- Given the error, then the New Conversation control is visibly emphasized so recovery is a single click

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
| 4 | Settle Up | Select matching Venmo transactions, click "Mark as settlement" | Settlement linked — remaining balance $0.00 |
| 5 | Budget | Navigate to Budget for March, toggle to YTD | Food & Dining at 92% (amber), Travel at 40% (teal) |
| 6 | Budget | Discuss — agree to eat out less next month | — |
| 7 | Budget | See "Set up April budgets?" prompt, click it | Month picker advances to April |
| 8 | Budget | See "Copy budgets from March" card, click it | April budgets created instantly |
| 9 | Budget | Tap Food & Dining, edit amount from $800 to $700 | Budget updated for April only |
| 10 | Settle Up | Return to Settle Up for March, click Lock Month | March finalized, lock indicator appears |
| 11 | Dashboard | Return to Dashboard | March locked; April budgets ready |

### Journey 4: Budget Review

| Step | Screen | Action | Result |
|---|---|---|---|
| 1 | Budget | Navigate to Budget for current month | If budgets set: groups with progress bars. If empty: copy card or add-first-budget |
| 2 | Budget | (If empty) Click "Copy budgets from [month]" | Budgets appear instantly, summary stats populate |
| 3 | Budget | Scan urgency-sorted groups | Over-budget groups at top (coral), near-limit (amber), on-track (teal) |
| 4 | Budget | Toggle to YTD | Cumulative spending with gap indicators per group |
| 5 | Budget | Expand "Food & Dining" | Per-category breakdown with include_personal toggles |

### Journey 5: Settings & Configuration

| Step | Screen | Action | Result |
|---|---|---|---|
| 1 | Settings | Navigate to Settings | Sections: Theme, Categories, People |
| 2 | Settings | Toggle theme to Dark | App switches immediately |
| 3 | Settings | See "Unmapped: Coffee Shops & Treats" | New category from recent upload |
| 4 | Settings | Assign to "Food & Dining" group | Mapping saved |
| 5 | Settings | Set adjustment account: "Shared Adjustments" | Enables export on Transactions page |

### Journey 6: First-Time Budget Setup

| Step | Screen | Action | Result |
|---|---|---|---|
| 1 | Budget | Navigate to Budget for first month with data | "Add your first budget" empty state — no previous month to copy from |
| 2 | Budget | See unbudgeted spending below empty state | Groups with actual spending and average hints as context |
| 3 | Budget | Click "Add budget", select "Food & Dining" | Amount input with hint: "Avg: $750/mo" |
| 4 | Budget | Enter $800, save | Food & Dining appears with progress bar |
| 5 | Budget | Add budgets for remaining groups | ~5 minutes, guided by average spending hints |
