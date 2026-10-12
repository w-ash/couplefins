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

## External read interface

Epic. The maintainer (2026-10-03): couplefins is the source of truth for the couple's finances, and other
tools read it through one generic interface. Monarch CSVs are how data arrives for now, not the
model: a bank's own statement, a direct bank feed, or another aggregator can replace them. The
first consumer is a private sync tool that fills a joint account's log in a spreadsheet from
couplefins. Nothing here is specific to that consumer: the account is one joint account, and a
budget line is one tag namespace.

**Shape options**

| Option | For | Against |
|---|---|---|
| HTTP JSON under `/api/ext/v1` on the deployed app | Already hosted at couplefins.fly.dev with one instance and one database; a consumer needs a URL and a token, nothing else; works the same from the maintainer's Mac and from a hub; FastAPI generates the OpenAPI schema per version; routes stay 5-10 lines over existing use cases | Needs non-browser auth (story below); each call wakes Neon |
| CLI with JSON stdout (`python -m src.interface.cli`) | Matches how a sync tool shells out to other CLIs | Every consumer machine needs a checkout, Python 3.14, and `DATABASE__URL`, which brings back the version drift the v1.1.1 schema guard exists for |
| Python package import | No transport | Couples consumers to `src/` internals and async SQLAlchemy; consumer holds database credentials |
| The MCP server (v1.9.3) | Already exists and exposes reads and writes | Shaped for agents: chat-shaped results, two-phase confirmation, no versioned contract. It stays the surface for Claude sessions |

**Recommendation: HTTP.** It is the only option where the consumer holds no database
credentials and no copy of the code, and the only one that already runs where a future hub
could reach it.

**Shared rules for every story here**

- New router `src/interface/api/routes/ext.py` with its own schemas in
  `src/interface/api/schemas/ext/`, mounted at `/api/ext/v1`. It never shares response models with
  `/api/v1`, which is the web UI's private contract and changes with every Orval regeneration.
- Read-only first. No ext route mutates. Writes (tagging a transaction from a consumer) come
  later, as a separate story with a `write` scope, reusing `BulkModifyTagsUseCase`.
- Versioning: within v1 only additive changes (new endpoints, new optional fields, new optional
  query params). A removed field, renamed field, or changed meaning is `/api/ext/v2`, and v1 stays
  served until its consumers move. `GET /api/ext/v1/meta` returns `api_version` (`"1.<minor>"`),
  bumped on each additive change and noted in `CHANGELOG.md`.
- Money is a decimal string (`"-5299.00"`), signed per the existing convention (negative = out).
  Dates are ISO `YYYY-MM-DD`.

- [ ] **Importers behind one interface**
    - Effort: M
    - What: Every import goes into a couplefins account through one `Importer` protocol that
      turns a source into source-neutral rows. Monarch CSV is the first importer and a bank
      statement CSV the second; a direct bank feed or another aggregator is a later one.
    - Why: `upload_csv.py` calls `parse_monarch_csv` directly and every `Upload` belongs to a
      person, so couplefins can only learn what one person's Monarch saw. A joint account has no
      such person, and Monarch may not stay the source.
    - Dependencies: None
    - Status: Not Started
    - Notes:
        - `src/domain/parsing/importer.py`: `Importer` protocol, `parse(data: bytes, ctx:
          ImportContext) -> ParseResult`, with rows carrying date, amount, merchant,
          original statement, notes, tags, and the account they belong to.
          `src/domain/parsing/monarch_csv.py` becomes `MonarchCsvImporter` unchanged in behaviour;
          its tag rules (`_classify`) stay Monarch-specific.
        - `BankStatementCsvImporter`: one column map per account (date, amount or debit/credit,
          description, memo), stored with the account, so a new bank is configuration, not code.
        - `Upload` gains `account_id`, `importer`, and `content_sha256`. Importing a file whose
          hash this account already has is refused with the earlier import's date, so the same
          statement never lands twice. An overlapping statement (a new file that repeats some
          rows) is matched row by row on the account's natural key, as `src/domain/dedup.py`
          does today.
        - The existing "Automatic CSV format detection" idea under Data & Import builds on this.
        - Acceptance: a Monarch CSV imports with results identical to today's (the existing
          upload tests pass unchanged); a bank statement CSV imports into its account through its
          column map; the same file imported twice is refused; a statement overlapping the last
          one adds only its new rows.

- [ ] **Service tokens for non-browser consumers**
    - Effort: S
    - What: Named, revocable bearer tokens with scopes (`read` only for now), checked by a new
      `get_service_principal` dependency that only `/api/ext/*` routes use.
    - Why: The only auth today is the JWT cookie from a person's name and password
      (`get_current_user` in `src/interface/api/dependencies.py`). A launchd job cannot log in,
      and should not hold a person's password.
    - Dependencies: None
    - Status: Not Started
    - Notes:
        - Table `service_tokens (id, name, scopes, token_hash, created_at, last_used_at,
          revoked_at)`; Alembic migration plus `SCHEMA_VERSION` bump. Store a SHA-256 of the
          token (it is high-entropy), never the token.
        - Create and revoke from a CLI run with `DATABASE__URL`:
          ```sh
          uv run python -m src.interface.cli tokens create sync-tool --scope read   # prints the token once
          uv run python -m src.interface.cli tokens revoke sync-tool
          uv run python -m src.interface.cli tokens list
          ```
        - Header `Authorization: Bearer cf_<token>`. A token never authenticates `/api/v1`, and a
          session cookie never authenticates `/api/ext`.
        - Acceptance: a created token reads `/api/ext/v1/meta`; a revoked or unknown token gets
          401; a `read` token on a future write route gets 403; `/api/v1/*` with a bearer token
          and no cookie gets 401; `last_used_at` moves on use.

- [ ] **Read API v1**
    - Effort: M
    - What: Read-only endpoints for accounts, transactions (with split, payer, and per-person
      shares), settlements with their portions, and per-person balances, over a date range.
    - Why: One stable contract that a sync tool, an agent session, or any later tool reads, so none of
      them reaches into the database or the web UI's routes.
    - Dependencies: Service tokens for non-browser consumers; Jointly owned accounts (Co-owned
      home epic)
    - Status: Not Started
    - Notes:
        - Owner shares (Co-owned home epic) reach the API later as an additive v1 change.
        - Endpoints:
          ```
          GET /api/ext/v1/meta
              -> {api_version, app_version, persons: [{id, name}],
                  accounts: [{id, name, kind, owner_person_id}]}
          GET /api/ext/v1/transactions?from=YYYY-MM-DD&to=YYYY-MM-DD[&account_id=][&tag=][&tag_prefix=]
          GET /api/ext/v1/settlements?year=YYYY
          GET /api/ext/v1/balances?year=YYYY
          ```
        - Transaction fields: `id`, `account_id`, `date`, `amount`, `merchant`, `category`,
          `category_group`, `group_kind`, `original_statement`, `notes`, `tags`,
          `payer_person_id` (null on a joint row), `payer_percentage`,
          `shares: [{person_id, percentage, amount}]`, `depositor_person_id`, `household`,
          `is_settlement`, `is_excluded`, `month_finalized`, `import_id`.
        - `id` is the `Transaction.id` UUID. It survives a re-import while the row's natural key
          matches (`natural_key` in `src/domain/dedup.py`); a row a re-import removes and a
          later one brings back gets a new id. The v1 contract says so: consumers key on `id`
          and treat a vanished id as removed.
        - Range cap 366 days, no pagination (about 200 rows a month). Transaction lists are read
          only through `src/application/use_cases/_shared/transaction_reads.py` (grep gate); add a
          date-range, account, and tag-prefix read there. `SearchTransactionsCommand` is
          month-scoped with a limit, so it does not fit as is.
        - Balances come from `GetSettleUpData` (year and month balances, direction-resolved);
          settlements carry their portions (v1.11.0). No arithmetic in the route.
        - Contract test: export the `/api/ext/v1` subset of the OpenAPI schema
          (`scripts/export_openapi.py`) to a committed snapshot, and fail CI on a non-additive
          diff.
        - Acceptance:
            - With a `read` token, each endpoint returns the documented fields; the transaction
              figures for a month equal what Transactions and Settle Up show for it.
            - `shares` percentages sum to 100 and amounts sum to `amount` on every row.
            - Re-importing an unchanged file is refused and changes no `id`.
            - A range over 366 days, or `from` after `to`, gets 422.
            - Removing a field from a v1 schema fails the contract test.
            - Full quality gate green.

- [ ] **Namespaced tags for consumer labels**
    - Effort: S
    - What: Tags of the form `<namespace>:<value>` (for example `line:mortgage`) are labels for
      consumers: never treated as split, reserved, or person-name tags, kept across re-imports,
      and filterable with `tag_prefix` in the ext API.
    - Why: A joint account's log needs each row's budget line. A generic label lets any consumer
      group rows without couplefins knowing what a line is.
    - Dependencies: None
    - Status: Not Started
    - Notes:
        - The Monarch parser splits tags on commas only and lowercases them
          (`src/domain/parsing/monarch_csv.py`), so `line:mortgage` already survives a Monarch
          import. A bank statement has no tags, so its rows are tagged in couplefins: the bulk tag
          editor, or MCP `bulk_modify_tags`.
        - `tags` is in `_MUTABLE_FIELDS` (`src/domain/dedup.py`), so a re-import whose source
          lacks a tag added in couplefins proposes removing it. An import never removes a
          namespaced tag; v1.7.1's flag preservation is the precedent, so find its mechanism
          before choosing one.
        - Acceptance: `line:mortgage` on an `s50` row leaves the split at 50; a namespaced tag
          added in couplefins survives a re-import of a source without it;
          `GET /api/ext/v1/transactions?tag_prefix=line:` returns only rows carrying a `line:`
          tag.

## Co-owned home

Epic, an outline. The maintainer (2026-10-12): two people who co-own a home pay its costs from
joint bank accounts, and couplefins becomes where those payments are logged, with a spreadsheet
backup through the Read API. It also tracks each owner's share in the home as it grows, and any
transaction can be tagged as counting toward a share. These stories sketch the shape of that
work; they are not a spec.

**Before building anything here**

- Learn the owners' actual financial setup for the home first, from the maintainer and from the
  maintainer's private notes on it (ask where they are; nothing from them comes into this repo):
  the accounts, the loans and where each stands, the co-ownership agreement as signed, the
  decisions about who pays what, and what is already logged elsewhere.
- Don't assume these stories capture every requirement, or the situation as it stands when the
  work starts. They were written before the agreement was signed, while the purchase was financed
  by short-term loans awaiting a refinance, so both will have moved on.
- Revise the stories with the maintainer, then build. Where the setup and a story disagree, the
  setup wins.
- Keep the model generic, a co-owned asset with a capital account per owner, so it works for any
  couple. The household's rules, names, and figures are data entered in the app, never code,
  docs, fixtures, or commit messages (CLAUDE.md: public repo). Examples use Alice and Bob.

**The setup as understood on 2026-10-12** (confirm every point)

- Two joint accounts: checking, which pays the bills and the renovation (each owner has a debit
  card), and savings, whose named buckets set money aside (property tax, insurance, a repair
  reserve, renovation money not yet spent).
- Each owner deposits into checking from their own bank. Money given to one owner belongs to
  that owner wherever it sits, and some of it pays house costs.
- The co-ownership agreement sets each owner's share as their qualifying contributions divided
  by both owners' totals, dollar for dollar, with no interest or timing adjustment.
    - Qualifying: down payment and closing costs; interest and principal on loans both owners
      approved; property tax; insurance; necessary repairs above a threshold; other work only when
      both owners agreed its scope and cost split before it started. Nothing else counts unless
      both agree.
    - Not qualifying: utilities (split, but credited to no one), rent, and moving costs.
    - Each bill splits 50/50 by default. Either owner may pay more of a bill when both agree, and
      the extra counts toward the payer. An owner who covers the other's missed payment is
      credited with it.
    - On a sale or buyout, what is left after costs and loans splits by share.
- Money sitting in the accounts (the float, the set-asides, the reserve) is not a contribution
  until it pays a qualifying cost, and on a sale each owner gets back their unspent deposits. This
  was a proposed rule; check whether the signed agreement has it.
- Some qualifying payments never pass through the joint accounts: the closing, through escrow; a
  loan paydown wired from one owner's own account; a premium paid before the accounts opened; a
  house cost on a personal card.
- The owners cap how much of their own money goes into the renovation, apart from gifts and
  loans, so a contribution's source matters as well as its owner.
- Undecided at writing: whether refunds (a returned deposit, a rebate, an insurance refund) and
  payments a lender returns reduce credits, and how a loan settled for less than its face amount
  counts.

- [ ] **Jointly owned accounts**
    - Effort: L
    - What: An account is a first-class couplefins entity, personal (one owner) or joint. A joint
      account's transactions are imported straight into it, belong to no person's upload, never
      enter settlement, and carry per-owner shares set by rule or by hand.
    - Why: Today a transaction exists only as a row in one person's upload, with that person as
      `payer_person_id`. A payment from a joint account has no such payer: forcing one makes it
      that person's personal spending, or, split, a debt the other owes, though both funded the
      account.
    - Dependencies: Importers behind one interface
    - Status: Not Started
    - Notes:
        - The maintainer (2026-10-12): the earlier draft of this story is not the design to
          follow; work out what the setup needs (epic preface). The parts kept below are a
          starting point.
        - Table `accounts (id, name, kind: personal | joint, owner_person_id null for joint,
          importer, column_map)`; Alembic migration plus `SCHEMA_VERSION` bump. `Transaction`
          gains `account_id`; `payer_person_id` is null on a joint row. Existing Monarch rows map
          to a personal account per uploader and per Monarch `Account` string, so their figures do
          not move.
        - Joint rows are excluded from settlement at read time, as `exclude_non_spending` in
          `src/domain/filters.py` does for transfers.
        - A joint row's split can't come from the account alone: it follows whose money paid. A
          bill funded by both owners' deposits splits 50/50; work paid with money given to Alice
          is Alice's when both owners agreed it. So a split resolves from a rule (by tag or
          category), then the account default, and a row can override both (Funding sources and
          pots).
        - Transfers between the two joint accounts are transfer-kind on both legs, and so is an
          owner's personal leg of a deposit. Whether the bank's statement export shows moves
          between savings buckets: not checked.
        - Deposits carry `depositor_person_id`, matched by rule: the sending account where the
          statement shows it, else memo text, else assigned by hand in the app. The earlier draft
          assumed deposit memos name the depositor; check a real statement first. The sender is
          not always the owner: money given to Alice and passed on by her is hers.
        - The earlier draft had each person's lens (`src/domain/spending_lens.py`) take their
          share of every joint payment. Loan principal and improvements build equity rather than
          being spent; which joint rows count as spending is the maintainer's call.
        - Acceptance, to revise with the setup: a joint account's statement imports with no
          person's upload involved; its rows add nothing to any settlement balance; a row's shares
          come from its override, else its rule, else the account default; an unmatched deposit is
          listed for assignment; transfers between the joint accounts count as spending nowhere;
          Monarch-imported figures on every page are unchanged by the migration.

- [ ] **Funding sources and pots**
    - Effort: M
    - What: Each deposit into a joint account records whose money it is and its source (the
      owner's own money, or money given to that owner), and the money in the joint accounts is
      tracked by pot (bills, set-asides, renovation), so each payment traces to the money that
      paid it.
    - Why: A share credit goes to the owner whose money paid; an owner's cap on their own money
      leaves gifts out; unspent deposits go back to their depositor on a sale; and a bank's
      statement export may not show bucket balances.
    - Dependencies: Jointly owned accounts
    - Status: Not Started
    - Notes:
        - The simplest form may be namespaced tags on deposits and payments (`source:`, `pot:`)
          with balances computed, as adjustments are ("Why adjustments are computed, not stored",
          `docs/domain.md`). Confirm against the setup before choosing.
        - A payment from a pot takes the pot's owners unless the row says otherwise, and its
          credit follows the split both owners agreed for that cost.
        - Acceptance, to revise: per owner, deposits less their share of payments equals their
          unspent balance; each pot's computed balance matches the bucket balance the owners
          enter from the bank.

- [ ] **Owner shares in a co-owned asset**
    - Effort: L
    - What: Any transaction can be tagged as a qualifying contribution of a given kind; each
      owner's credit is their share of it; couplefins keeps each owner's running capital account
      and share percentage (their total divided by both totals) over time.
    - Why: The maintainer (2026-10-12): couplefins must track each owner's share in the home as
      it grows, and spending that goes to a share must be taggable. The agreement sets the share
      from these credits, and a sale or buyout splits by it.
    - Dependencies: Jointly owned accounts; Funding sources and pots; Namespaced tags for
      consumer labels
    - Status: Not Started
    - Notes:
        - Tags such as `share:closing`, `share:loan-interest`, `share:loan-principal`,
          `share:property-tax`, `share:insurance`, `share:repair`, `share:agreed-work`, and
          `share:none`. Namespaced, so a share tag never changes a split. Which kinds count, and
          the repair threshold, are settings, not code.
        - A row credits each owner with their share of its amount, whatever account it came
          from. A cost one owner pays from a personal account as an agreed extra contribution is
          `s100` or `household` (no settlement) and credits the payer in full.
        - Agreed work: the record shows the job, the split both owners agreed, and the date they
          agreed, which comes before the work starts. The repair threshold may apply to a whole
          repair billed over several invoices rather than to each invoice; confirm.
        - Reversals: a refund or returned payment, linked to the row it reverses, lowers that
          credit, if the owners decide refunds work that way (undecided at writing).
        - Shares are computed from rows, never stored, as settlement balances are.
        - Owner credits, capital accounts, and percentages reach the Read API as an additive v1
          change, for the spreadsheet backup.
        - Acceptance, to revise: a tagged row adds each owner's share of it to their capital
          account; the percentages sum to 100; an untagged or `share:none` row adds nothing; a
          utility bill split 50/50 adds nothing; each month's capital accounts equal the sum of
          credits through that month.

- [ ] **Share credits from outside the joint accounts**
    - Effort: M
    - What: Contributions that never pass through an imported account (a closing paid through
      escrow, a premium paid before the accounts opened, a payment from an account no one
      imports) are entered by hand, each with its date, amount, owner, kind, and the document
      that shows it.
    - Why: Some of the largest credits, the down payment and closing costs among them, come
      before the joint accounts exist or outside them.
    - Dependencies: Owner shares in a co-owned asset
    - Status: Not Started
    - Notes:
        - A manual entry could be a row in an account of its own (for example, "Escrow"), so every
          credit is still a row and shares have one computation path.
        - A payment from an owner's bank that their Monarch import already has is tagged there,
          not entered twice.
        - Acceptance, to revise: a manual credit with its document reference appears in the
          owner's capital account; deleting it removes the credit; no manual row enters
          settlement or budgets.
