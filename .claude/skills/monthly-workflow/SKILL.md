---
name: monthly-workflow
description: Couplefins monthly reconciliation workflow and domain concepts. Use when implementing features related to uploads, settlements, reconciliation, shared expenses, or the monthly ritual.
user-invocable: false
---

# Monthly Reconciliation Workflow

## Solo Prep (each person, days before together session)
1. Export Monarch CSV for the month (Settings > Data > Download Transactions)
2. Upload to Couplefins — previous data for same person+month is replaced on re-upload
3. Review shared transactions — fix miscategorized items, correct split percentages, bulk-edit tags
4. Check for unmapped categories → assign to groups in Settings

## Together Session (~15 minutes, side by side)
1. **Dashboard** — see who owes whom, check upload readiness
2. **Settle Up** — record payments against the running outstanding balance (Venmo, cash, etc.), or waive it; one catch-up payment can cover several months
3. **Budget** — monthly and YTD views, identify over-budget groups
4. **Finalize** — lock month (rejects further uploads/edits for that month)
5. (Optional) Export adjustment CSVs → import into Monarch for accurate personal spending

## Key Domain Concepts
- **`shared` tag**: marks a Monarch transaction as a shared expense
- **`sXX` tag** (e.g., `s70`): payer covers XX% of the expense (default 50/50 if absent)
- **Internal model**: `payer_person_id` + `payer_percentage` (0-100). Other person's share = `100 - payer_percentage`
- **Settlement math**: sum each person's share across all split transactions → per-month gross; a running ledger nets all-time gross minus all-time payments into one outstanding balance ("Person A owes Person B $X · covers Mar–May"). Payments apply FIFO oldest-month-first; a settlement's year/month is a display-only annotation
- **Amounts**: negative = expense, positive = income/refund (Monarch CSV convention, carried through entire stack)
- **Category groups**: ~12 groups rolling up ~75 Monarch categories. Budgets are per group, not per category
- **Finalization**: locks a month's transactions — uploads and edits rejected; payments stay possible and a skipped month's balance rides forward. Can un-finalize with confirmation
