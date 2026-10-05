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
first consumer is frigg, which fills the House account tab of the private house sheet
from couplefins (frigg backlog, "House account log from couplefins"). Nothing here is
house-specific: the house account is one joint account, and a budget line is one tag namespace.

**Shape options**

| Option | For | Against |
|---|---|---|
| HTTP JSON under `/api/ext/v1` on the deployed app | Already hosted at couplefins.fly.dev with one instance and one database; a consumer needs a URL and a token, nothing else; works the same from the maintainer's Mac and from a hub; FastAPI generates the OpenAPI schema per version; routes stay 5-10 lines over existing use cases | Needs non-browser auth (story below); each call wakes Neon |
| CLI with JSON stdout (`python -m src.interface.cli`, huginn-style) | Matches how frigg already shells out to huginn | Every consumer machine needs a checkout, Python 3.14, and `DATABASE__URL`, which brings back the version drift the v1.1.1 schema guard exists for |
| Python package import | No transport | Couples consumers to `src/` internals and async SQLAlchemy; consumer holds database credentials |
| The MCP server (v1.9.3) | Already exists and exposes reads and writes | Shaped for agents: chat-shaped results, two-phase confirmation, no versioned contract. It stays the surface for Claude sessions |

**Recommendation: HTTP.** It is the only option where the consumer holds no database
credentials and no copy of the code, and the only one that already runs where a future frigg hub
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
          uv run python -m src.interface.cli tokens create frigg --scope read   # prints the token once
          uv run python -m src.interface.cli tokens revoke frigg
          uv run python -m src.interface.cli tokens list
          ```
        - Header `Authorization: Bearer cf_<token>`. A token never authenticates `/api/v1`, and a
          session cookie never authenticates `/api/ext`.
        - Acceptance: a created token reads `/api/ext/v1/meta`; a revoked or unknown token gets
          401; a `read` token on a future write route gets 403; `/api/v1/*` with a bearer token
          and no cookie gets 401; `last_used_at` moves on use.

- [ ] **Jointly owned accounts**
    - Effort: L
    - What: An account is a first-class couplefins entity, personal (one owner) or joint (both).
      A joint account's transactions are imported straight into it, belong to no person's
      upload, never enter settlement, and split between its owners (50/50 by default).
    - Why: Today a transaction exists only as a row in one person's upload, with that person as
      `payer_person_id`. A joint account's mortgage payment has no such payer: forcing one makes
      it that person's personal spending, or, split, a debt the other owes, though both funded
      the account.
    - Dependencies: Importers behind one interface
    - Status: Not Started
    - Notes:
        - Table `accounts (id, name, kind: personal | joint, owner_person_id null for joint,
          default_split, importer, column_map)`; Alembic migration plus `SCHEMA_VERSION` bump.
          `Transaction` gains `account_id`; `payer_person_id` is null on a joint row. Existing
          Monarch rows map to a personal account per uploader and per Monarch `Account` string, so
          their figures do not move.
        - A joint row's shares come from the account's default split unless the row overrides it.
          It is excluded from settlement at read time, as `exclude_non_spending` in
          `src/domain/filters.py` does for transfers. Payments are household; each person's
          personal lens (`src/domain/spending_lens.py`) takes their share.
        - Deposits: a joint row with a positive amount from an owner carries
          `depositor_person_id`. A per-account rule matches the memo to a person (the house
          account's deposit memos name the depositor); a deposit no rule matches is listed for
          the couple to assign in the app.
        - The depositor's own side of a deposit, if it comes in through their personal import,
          stays a transfer-kind row, so it never counts as spending.
        - Acceptance: a bank statement CSV for a joint account imports with no person's upload
          involved; its rows add nothing to any settlement balance; a 50/50 payment adds half its
          amount to each person's personal spending; a deposit whose memo names a person has that
          person as depositor; Monarch-imported figures on every page are unchanged by the
          migration.

- [ ] **Read API v1**
    - Effort: M
    - What: Read-only endpoints for accounts, transactions (with split, payer, and per-person
      shares), settlements with their portions, and per-person balances, over a date range.
    - Why: One stable contract that frigg, a vault session, or any later tool reads, so none of
      them reaches into the database or the web UI's routes.
    - Dependencies: Service tokens for non-browser consumers; Jointly owned accounts
    - Status: Not Started
    - Notes:
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
    - Why: The house account needs each row's budget line. A generic label lets any consumer
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
