# Domain Knowledge

## Monarch Money

[Monarch Money](https://www.monarchmoney.com) is a personal finance app. Each person in the couple has their own Monarch account. They categorize transactions using a shared category structure.

### CSV Export Format

Monarch exports transactions via Settings > Data > Download Transactions. The CSV has these columns:

| Column | Description |
|---|---|
| Date | Transaction date |
| Merchant | Merchant name |
| Category | User-assigned category |
| Account | Bank/credit card account name |
| Original Statement | Raw statement description from the bank |
| Notes | User-added notes |
| Amount | Negative = expense, positive = income/refund |
| Tags | Comma-separated tags |

### Tag Conventions

The couple uses Monarch tags to classify transactions:

- **`shared`** or **`split`** tag (case-insensitive): marks a transaction as a household expense and defaults to a 50/50 split
- **`household`** tag (case-insensitive): marks a transaction as a household expense without implying a split — for expenses relevant to the couple's shared life but paid individually (e.g., concert tickets bought separately for an event you attend together)
- **`sXX`** tag (e.g., `s70`): sets the payer's share to XX%. Authoritative — overrides any default from other tags. If multiple `sXX` tags are present, the highest value wins (payer takes the most share)
- **Person name** tag (e.g., `bob`): marks a transaction as spotted — the payer fronted the money but the other person owes 100%. A spotted expense is the *beneficiary's* personal spending, so `household` stays false. Detected by matching tags against known person names (case-insensitive). Reserved tags (`shared`, `split`, `household`, `settlement`) are never treated as person names.
- **`settlement`** tag (case-insensitive): marks a transaction as a settlement payment (e.g., Venmo transfer to your partner). Sets `is_settlement=true`, which excludes the transaction from both spending totals and budget calculations. You can also link settlement transactions from the Settle Up page instead of tagging in Monarch.
- Tags are dynamic — any integer 0-100 is valid for `sXX` (e.g., `s0`, `s30`, `s100`)

**Input vs. internal representation**: Tags are the *input mechanism*. Internally, each transaction stores two fields: `payer_person_id` (who paid), `payer_percentage` (their share, 0-100, always set), and `household` (budget-relevant to the couple, bool).

| Tags | `household` | `payer_percentage` | Type |
|---|---|---|---|
| (none) | false | 100 | Personal |
| `shared` or `split` | true | 50 (default) | Shared |
| `shared, sXX` | true | XX | Shared (custom split) |
| `shared, s100` | true | 100 | Household (no settlement) |
| `household` | true | 100 (no split implied) | Household (no settlement) |
| `household, sXX` | true | XX | Household + split |
| `sXX` alone | false | XX | Personal split |
| person-name (e.g., `bob`) | false | 0 | Spotted |
| person-name + `sXX` | false | XX | Personal split (sXX overrides spotted) |
| `settlement` | false | 100 | Settlement payment |

The `settlement` tag also sets `is_settlement=true`, which excludes the transaction from both reconciliation math and budget totals.

The couple can set splits either way: tag transactions in Monarch before exporting, or edit split percentages and household flags directly in the app after uploading. Both workflows produce the same internal representation.

### Reconciliation Math

For each transaction where `payer_percentage < 100`:
- `payer_share = |amount| × (payer_percentage / 100)`
- `other_share = |amount| × ((100 - payer_percentage) / 100)`

Sum across all settlement-relevant transactions for a period (a single month or an arbitrary date range) → net result: "Person A owes Person B $X"

That per-period sum is a month's **gross position**. Actual settlement runs on **explicit coverage** (v1.11.0): every settlement records the exact months it covers as a list of **(year, month, amount) portions** summing to the settlement amount. Coverage is never inferred, and portions are the only mechanism:

- **Monthly rent transfer** — one portion: $1,981 covering its rent month. (In real life this is three transactions — the rent Check of −$3,962 split 50/50 plus both Venmo transfer legs of $1,981 — the legs are linked to the settlement and excluded from reconciliation; the portion records which month the payment covers.)
- **Catch-up lump** — several portions, one per covered month, allocated at record time in Python (oldest covered month first, remainder on the last covered month) and stored. Because rent in the covered months is usually already settled, their residuals may run toward the payer — the lump's portions settle that net, whichever direction it runs.
- A **waiver** is a settlement portioned across the waived year's months.
- A payment recorded with no coverage defaults to one portion at its `settled_at` month.

Derived numbers, all computed in Python and served precomputed and direction-resolved (the UI does no arithmetic):

- **Month balance** = net of its charges' shares − portions allocated to it.
- **Year balance** = sum of its month balances. The Settle Up page shows one year at a time; no all-time figure appears anywhere on it. A January transfer whose portions cover the previous December counts toward the old year.
- Display math is purely additive: every dollar is allocated to a month when the settlement is recorded, and portions are never reallocated afterward.
- Multiple payments per month are first-class, and payments are not bound to when they were sent: a rent transfer on the 1st, a skipped month, and one catch-up lump all take their meaning from the portions they record.

**Examples**:
- Alice pays $100 dinner, tagged `shared` (no sXX → 50/50): Alice's share $50, Bob's share $50. Bob owes Alice $50.
- Bob pays $200 rent, tagged `shared, s70`: Bob's share $140, Alice's share $60. Alice owes Bob $60.
- Alice pays $30 for Bob's parking ticket, tagged `bob` (spotted → 0%): Alice's share $0, Bob's share $30. Bob owes Alice $30.
- Alice pays $60 for her own concert ticket, tagged `household`: payer_percentage=100, so this does NOT enter settlement. Nobody owes anyone. (It does count toward the Lifestyle budget because `household=true`.)

## Transaction Classification

Transaction classification uses two orthogonal fields — one for settlement, one for budget:

- **`payer_percentage: int`** (0-100, always set, default 100) — the payer's share of this expense. Determines settlement math. The other person's share is always `100 - payer_percentage`.
- **`household: bool`** (default false) — whether this transaction is relevant to the couple's shared life. Determines budget inclusion.

Neither field implies the other. A transaction can be household without being split (concert you attended together but paid separately), or split without being household (unusual, but the fields are independent).

| Type | `household` | `payer_percentage` | Settlement? | Budget? |
|---|---|---|---|---|
| Personal | false | 100 | No | Only if category has `include_personal` |
| Shared | true | 1-99 | Yes (split) | Yes |
| Spotted | false | 0 | Yes (100% reimbursement) | Beneficiary's personal (not household) |
| Household (no split) | true | 100 | No | Yes |

**Spotted**: One person pays for something that is entirely the other person's expense — their subscription, their parking ticket, a hat they forgot their wallet for. The payer fronts the money and gets 100% back at settlement. It's the beneficiary's personal spending — a debt, not a household expense — so it never counts toward the household budget.

**Confirmed definitions** (2026-07-02): *household* = something the couple did together, regardless of who paid. *Personal* = not household — spending for yourself. *Spotted* = personal spending where one partner paid for the other; it attributes to the beneficiary's personal spending. *Settlement* is orthogonal to all of it: any `payer_percentage < 100` transaction enters settlement math, household or not — if Bob pays for Alice, Alice pays it back either way.

**Household (no split)**: An expense relevant to the couple's shared life but paid individually — concert tickets bought separately for a show they attend together, or groceries one person picked up but isn't splitting. Tagged `household` (or `shared, s100`) in Monarch. No settlement impact, but counts toward the shared budget.

### Settlement vs. budget

Settlement and budget are separate concerns:

- **Settlement**: Any transaction with `payer_percentage < 100` enters reconciliation math. The split determines each person's share. The `household` flag is irrelevant to settlement.
- **Budget**: Any transaction with `household=true` counts toward its category group's budget. Additionally, individual categories can be configured with `include_personal=true` to also count personal (`household=false`) transactions in that category's budget totals. This lets the couple track total spending in categories like Groceries across both people, even when some purchases weren't tagged as household.

## User Identity

Two named profiles (no authentication). Each person selects their identity once at first launch via a profile picker; the choice persists in localStorage across sessions. Each person uses their own laptop — identity switching is rare.

## Category Groups

Monarch Money has ~75 transaction categories (e.g., "Groceries & Home Supplies", "Dining Out", "Coffee Shops & Treats"). These roll up into ~12 **category groups** for budget tracking and reconciliation summaries:

- **Food & Dining**: Groceries, dining out, fast food, coffee, food delivery
- **Home Expenses**: Rent, water, gas & electric, internet, phone, other home expenses
- **Auto & Transport**: Gas, parking & tolls, insurance, ride shares, public transit
- **Travel**: Flights, hotels & Airbnb, rental cars, travel transportation
- **Playa**: Food, medical, supplies, hikes & walks, fun stuff
- **Shopping**: Clothing, house things, plants & garden, electronics
- **Health & Wellness**: Medical, fitness, personal care, supplements, therapy
- **Lifestyle**: Movies, streaming, concerts, apps & subscriptions, news, alcohol & bars
- **Festivals**: Infrastructure, tickets, consumables, outfits, transportation
- **Gifts & Donations**: Charity, gifts
- **Financial**: Loans, fees, cash & ATM, taxes

Each Monarch category maps to exactly one group. The initial mapping is seeded from a JSON fixture file (`data/category_groups.json`) and can be updated via the app as new categories appear.

## Category Group Budgets

Monthly budget limits per **category group** (not individual category). Each budget is a simple per-month amount identified by `year` + `month` — no cascading effective dates.

**Household vs personal budgets**: Household budgets use `person_id=NULL` and are shared — editable by either partner. Personal budgets use the authenticated user's `person_id` and are private per-person. The two are completely separate views controlled by a scope toggle.

The couple reviews budgets together once a month. The system supports two views:

- **Monthly**: Current month's spending vs. the monthly budget amount per group.
- **Year-to-date (YTD)**: Cumulative spending from January through the current month vs. the YTD budget (sum of individual monthly amounts where a budget was set). A month with no budget record contributes $0 to the YTD total.

## Accounting Concepts Mapping

Couplefins vocabulary mapped to standard accounting terms:

| Couplefins Term | Accounting Equivalent | Notes |
|---|---|---|
| Transaction | Source Document / Bank Statement Line | Imported from Monarch CSV |
| Person | Account Holder | Implicit account — each person accumulates a running balance |
| Upload | Batch Import / Document Provenance | Audit trail for data ingestion |
| ReconciliationPeriod | Transaction Lock | Freezes a month's data (uploads/edits rejected) — not a balance scope; settlements covering the month can still be recorded |
| CategoryGroup | Chart of Accounts (level 1) | Reporting hierarchy |
| CategoryMapping | Posting Rule | Routes categories to groups |
| Adjustment (v0.3.x) | Correcting Entry (Reversal pattern) | Offsetting entries for accurate per-person spend |
| Settlement | Payment with recorded coverage | Records that Person A paid Person B (amount, method, notes) plus a list of (year, month, amount) portions summing to the amount — the exact months the payment covers, allocated at record time and stored. Linked transfer transactions excluded from reconciliation. |
| `payer_percentage` | Allocation Rule / Split Ratio | Determines each person's share (0-100, always set). Settlement: any transaction where `payer_percentage < 100` |
| `household` | Expense Classification | Per-transaction flag — "relevant to the couple's shared life." Set by `shared`, `split`, or `household` tags (person-name tags do NOT set it — spotted is the beneficiary's personal spending) |
| `include_personal` | Budget Scope Flag | Per-category toggle to also include personal (non-household) transactions in budget totals |
| `is_finalized` | Period Close | Prevents modification of a month's transactions after agreement; settlements covering the month stay possible |
| TransactionEdit | Audit Log Entry | Records post-upload changes to a transaction (field, old value, new value, timestamp) |

### Signed-amount convention

Amounts follow the Monarch CSV convention: **negative = expense, positive = income/refund**. This carries through the entire stack — domain entities, reconciliation computations, and future Monarch CSV export. No unsigned-amount + debit/credit translation layer.

### Why no double-entry bookkeeping

With exactly two people, every credit to one is a debit to the other. The zero-sum invariant is guaranteed by construction — there is no third party who could break the balance. A full double-entry ledger (accounts, journal entries, book entries) would triple persistence complexity for zero correctness gain.

### Why adjustments are computed, not stored

Reconciliation summaries and adjustment entries are derived on-the-fly from source transactions. With ~100-200 transactions/month, full-scan computation is instant. Storing computed data would create cache-invalidation problems when source transactions change (re-uploads, corrections).
