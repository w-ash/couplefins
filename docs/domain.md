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

### Shared Expense Conventions

The couple uses Monarch tags to mark shared expenses:

- **`shared`** tag (case-insensitive): marks a transaction as a shared expense
- **`sXX`** tag (e.g., `s70`): overrides the default 50/50 split. The number means "the person who paid covers XX% of this expense." If no `sXX` tag is present, the split is 50/50.
- Tags are dynamic — any integer 0-100 is valid (e.g., `s0`, `s30`, `s100`)

**Input vs. internal representation**: The `sXX` tag is the *input mechanism* — how the system learns the split from a Monarch CSV. Internally, each transaction stores `payer_person_id` (who paid) and `payer_percentage` (their share, 0-100). The other person's share is always `100 - payer_percentage`. This makes the internal model agnostic to how the split was originally specified.

> **Note**: Today the couple manually enters split percentages in a spreadsheet. In the future, they will use Monarch `sXX` tags. The app's internal model supports either workflow.

### Reconciliation Math

For each shared transaction:
- `payer_share = |amount| × (payer_percentage / 100)`
- `other_share = |amount| × ((100 - payer_percentage) / 100)`

Sum across all shared transactions for a month → net result: "Person A owes Person B $X"

**Examples**:
- Alice pays $100 dinner, tagged `shared` (no sXX → 50/50): Alice's share $50, Bob's share $50. Bob owes Alice $50.
- Bob pays $200 rent, tagged `shared, s70`: Bob's share $140, Alice's share $60. Alice owes Bob $60.

## User Identity

Two named profiles (no authentication). Users select who they are when uploading a CSV.

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

Monthly budget limits per **category group** (not individual category) for shared expenses. Budget amounts have an `effective_from` date to support changing budgets over time without losing history.

The couple reviews budgets together once a month. The system supports two views:

- **Monthly**: Current month's spending vs. the monthly budget amount per group.
- **Year-to-date (YTD)**: Cumulative spending from January through the current month vs. the YTD budget (monthly_amount × months elapsed). When a budget's `effective_from` changes mid-year, the YTD calculation uses the correct amount for each month.

## Accounting Concepts Mapping

Couplefins vocabulary mapped to standard accounting terms:

| Couplefins Term | Accounting Equivalent | Notes |
|---|---|---|
| Transaction | Source Document / Bank Statement Line | Imported from Monarch CSV |
| Person | Account Holder | Implicit account — each person accumulates a running balance |
| Upload | Batch Import / Document Provenance | Audit trail for data ingestion |
| ReconciliationPeriod | Accounting Period | Open/closed, monthly granularity |
| CategoryGroup | Chart of Accounts (level 1) | Reporting hierarchy |
| CategoryMapping | Posting Rule | Routes categories to groups |
| Adjustment (v0.3.x) | Correcting Entry (Reversal pattern) | Offsetting entries for accurate per-person spend |
| `payer_percentage` | Allocation Rule / Split Ratio | Determines each person's share |
| `is_finalized` | Period Close | Prevents modification after agreement |

### Signed-amount convention

Amounts follow the Monarch CSV convention: **negative = expense, positive = income/refund**. This carries through the entire stack — domain entities, reconciliation computations, and future Monarch CSV export. No unsigned-amount + debit/credit translation layer.

### Why no double-entry bookkeeping

With exactly two people, every credit to one is a debit to the other. The zero-sum invariant is guaranteed by construction — there is no third party who could break the balance. A full double-entry ledger (accounts, journal entries, book entries) would triple persistence complexity for zero correctness gain.

### Why adjustments are computed, not stored

Reconciliation summaries and adjustment entries are derived on-the-fly from source transactions. With ~100-200 transactions/month, full-scan computation is instant. Storing computed data would create cache-invalidation problems when source transactions change (re-uploads, corrections).
