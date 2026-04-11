# Chat Assistant

The chat assistant lets either partner ask natural-language questions about their shared finances and get instant answers — without navigating to the right page, picking the right month, or reading the right table. It runs inside the app as a side panel on desktop and a full-screen page on mobile.

For the data model and accounting concepts behind the answers, see [domain.md](domain.md). For the monthly workflow the assistant supports, see [user-flows.md](user-flows.md).

---

## The Problem

Couplefins answers two core questions: **"Who owes whom?"** (settlement) and **"Are we on track?"** (budget). Both answers are already in the app, but getting to them requires knowing which page to open, which month to select, and which section to read. During the couple's together session — when they're reviewing finances side by side — these small navigation costs add up.

The chat assistant is a shortcut. It answers questions like "Who owes whom for March?" or "Are we on budget for dining?" directly, using the same data and logic as the existing pages. It doesn't unlock new capabilities — everything it can do is already available through the UI. It just makes the common questions faster.

---

## How It Works

The assistant uses Claude (Anthropic's LLM) with tool calling to query the app's existing data layer. The flow:

```
User types a question
        |
        v
Frontend sends message history ──POST /api/v1/chat──> Backend
                                                          |
                                                          v
                                               Build system prompt
                                               (identity, domain model,
                                                category groups, today's date)
                                                          |
                                                          v
                                               Stream to Claude API
                                               (Sonnet 4.6, effort: medium)
                                                          |
                                              +-----------+-----------+
                                              |                       |
                                         text delta              tool_use block
                                              |                       |
                                         SSE: token              Execute tool
                                              |                  (use case query)
                                              |                       |
                                              |                  SSE: tool_result
                                              |                       |
                                              |              Feed result back to Claude
                                              |                       |
                                              +-------<-------<-------+
                                              |
                                         SSE: done
                                              |
                                              v
                              Frontend renders streamed response
```

The backend runs an **agentic loop**: it streams Claude's response token by token, and when Claude decides to call a tool, the backend executes the tool (a query against the database via an existing use case), feeds the result back to Claude, and resumes streaming. Claude may call multiple tools in parallel within a single turn, and may loop through several tool rounds before producing a final answer. The loop caps at 8 rounds.

The frontend is a simple SSE consumer — it receives text deltas, tool-start indicators ("Looking up settlement..."), and tool-result summaries as they happen, and renders them in the chat panel.

---

## Tools

### Read-only tools

Each read-only tool is a thin wrapper around an existing query use case.

| Tool | What it returns | Backs which use case |
|---|---|---|
| `get_settlement_balance` | Who owes whom for a given month, gross and remaining balance, upload status per person, finalization state | `GetSettleUpDataUseCase` |
| `get_budget_overview` | Per-group budget progress: monthly amount, actual spending, YTD totals, health status (on_track / near_limit / over_budget) | `GetBudgetOverviewUseCase` |
| `search_transactions` | Up to 20 household transactions matching optional filters (merchant substring, category group, tag), with id, date, amount, payer, and split details | `SearchTransactionsUseCase` |
| `get_spending_by_group` | Spending totals per category group for a month (simpler than budget overview — no budget comparisons) | `GetBudgetOverviewUseCase` (different projection) |
| `get_spending_trends` | Monthly spending per group across a full year, with optional year-over-year comparison | `GetSpendingTrendsUseCase` |
| `get_dashboard_status` | Whether each person has uploaded their CSV, transaction count, finalization state, unmapped category count | `GetSettleUpDataUseCase` |

Tool results are projected into concise summaries (group name + spent + budget + health), not raw entity dumps. The model needs digestible context, not 200 transaction rows.

### Mutation tools (v1.5.2)

Mutation tools propose changes via a two-phase confirmation protocol — they never execute directly. Each returns `{status: "pending_confirmation", action_id, description, details}` and the change only executes when the user clicks Confirm.

| Tool | What it proposes | Backs which use case |
|---|---|---|
| `update_budget` | Create or update a category group budget for a specific month and scope (household/personal) | `SaveBudgetUseCase` |
| `update_transaction_split` | Change the payer split percentage on a single transaction (must reference a transaction ID from `search_transactions`) | `UpdateTransactionSplitsUseCase` |
| `bulk_update_transactions` | Bulk field changes (household flag, split, category, tags) on up to 100 transactions | `BulkUpdateTransactionsUseCase` / `BulkModifyTagsUseCase` |

Mutation tools validate inputs and check finalization before creating a pending action. If the target month is finalized, the tool returns an error prompting the user to unfinalize first.

---

## Design Decisions

### Why backend-orchestrated, not client-side

The agentic loop (call Claude, execute tools, feed results back) runs server-side. The frontend never talks to the Claude API directly. This keeps the API key on the server, lets tool execution use the same database access as the rest of the app, and means the frontend is just a streaming text renderer — the same SSE consumer pattern used elsewhere in the app.

### Why ephemeral conversations

Conversations aren't persisted. The chat panel starts fresh on page refresh. The couple asks quick questions during solo prep or the together session — they don't need searchable chat history. If usage patterns change, conversation persistence can be ported from the sister project (Mimir) which has it built.

### Why two-phase confirmation for mutations

Mutation tools (v1.5.2) use a two-phase confirmation protocol: the model proposes a change, the frontend renders a Confirm/Cancel card, and the change only executes on explicit user confirmation. Human-in-the-loop is the primary security control — the model can never silently modify financial data. Proposed actions are stored server-side in a `PendingActionStore` (in-memory dict with 5-minute TTL, keyed by UUID). The store validates that the confirming user matches the action creator.

### Why an in-memory pending action store

With exactly 2 users and a 5-minute TTL, an in-memory dict is sufficient. Actions are lost on server restart, which is acceptable — the user simply re-asks. No Redis, no database table, no background cleanup thread. The `_evict_expired()` method runs on every `create`/`claim` call.

### Why Sonnet 4.6, not Opus or Haiku

Claude Sonnet 4.6 hits the sweet spot for this use case: near-Opus tool routing accuracy at 1/5 the cost. Haiku is cheaper but less reliable at multi-tool selection — not worth the risk when the model is querying real financial data. The model ID is a single constant in `ChatConfig`, easy to swap if pricing or capabilities shift.

### Why effort: medium

Sonnet 4.6 defaults to `effort: high`, which adds latency from deeper reasoning. For a chat assistant answering "who owes whom?" — where the hard work is done by the tools, not the model's reasoning — `medium` effort gives fast responses without sacrificing tool routing quality.

### Why prompt caching

The system prompt and tool definitions are identical on every request. With prompt caching, the first request writes them to Anthropic's cache (2356 tokens), and every subsequent request within 5 minutes reads from cache at 10% of the input token cost. The system prompt's domain model section is intentionally thorough to clear Sonnet 4.6's 2048-token caching minimum.

### Why a side panel, not a page

The chat panel lives alongside the current page content — it compresses `<main>` rather than overlaying or navigating away. This follows the pattern used by GitHub Copilot and Cursor for secondary assistants alongside complex primary tasks. The left sidebar's mental model is "navigate to a page"; adding a chat item there would break that pattern. On mobile, chat is a full-screen page at `/ask` (accessible from the More menu) since side panels don't work at narrow widths.

---

## Configuration

One environment variable controls whether chat is available:

```
CHAT__ANTHROPIC_API_KEY=sk-ant-...
```

When set, the backend creates an `AsyncAnthropic` client at startup and the health endpoint reports `chat_available: true`. The frontend reads this flag and conditionally renders the chat icon tab and mobile nav entry.

When unset, the chat endpoint returns 503 (`CHAT_UNAVAILABLE`), the icon tab doesn't render, and the `/ask` route doesn't appear in the mobile menu. The rest of the app works identically.

Full config (all have sensible defaults):

| Setting | Default | Description |
|---|---|---|
| `CHAT__ANTHROPIC_API_KEY` | `None` | Anthropic API key. Chat is disabled when absent. |
| `CHAT__MODEL_ID` | `claude-sonnet-4-6` | Model to use for chat completions. |
| `CHAT__MAX_TURNS` | `8` | Maximum tool-calling rounds per request before bailing. |

---

## SSE Event Protocol

The chat endpoint streams responses as server-sent events. Each event is a JSON object on a `data:` line:

| Event type | Payload | When |
|---|---|---|
| `token` | `{"type": "token", "text": "..."}` | Each text fragment as the model generates it |
| `tool_start` | `{"type": "tool_start", "name": "get_settlement_balance", "id": "toolu_..."}` | When the model invokes a tool (before execution) |
| `tool_result` | `{"type": "tool_result", "name": "...", "summary": {...}, "is_error": false}` | After a tool executes (summary of the result) |
| `done` | `{"type": "done"}` | Stream completed successfully |
| `error` | `{"type": "error", "code": "...", "message": "..."}` | Something went wrong |

The frontend renders `token` events as streaming text, `tool_start` as inline progress indicators ("Looking up settlement..." for queries, "Proposing budget update..." for mutations), and `tool_result` as resolved indicators ("Checked settlement") or confirmation cards.

### Confirmation via `tool_result`

Mutation tools reuse the existing `tool_result` event type. When the summary contains `"status": "pending_confirmation"`, the frontend renders a `ConfirmationCard` instead of a normal result card. No new SSE event type is needed.

The confirmation flow uses an optional `confirmation` field on `ChatRequest`:

```json
{
  "messages": [...],
  "confirmation": { "action_id": "uuid", "approved": true }
}
```

When present, the backend intercepts the confirmation before the Claude loop, executes (or cancels) the pending action, injects the result into the conversation, and streams Claude's acknowledgment.

---

## System Prompt Structure

The system prompt uses XML tags for structure (Claude is trained to parse them) and includes:

- **`<identity>`** — the current user's name, their partner's name, today's date
- **`<scope>`** — constrains the assistant to Couplefins domain only; declines off-topic requests
- **`<category_groups>`** — the configured category group names (compact list)
- **`<domain_model>`** — a thorough primer on household vs personal, payer_percentage, settlement math, budget tracking, and the monthly workflow
- **`<response_format>`** — output style rules: plain text with `$` and `%`, markdown tables only for 3+ rows, concise answers, concrete follow-up suggestions
- **`<mutation_rules>`** — behavioral constraints for mutation tools: one mutation per turn, always confirm, check finalization, never fabricate IDs

The domain model section is intentionally detailed — it teaches the model enough context to answer follow-up questions without redundant tool calls, and it pushes the token count above the prompt caching threshold.

No user-generated content (merchant names, transaction notes) appears in the system prompt. That data flows exclusively through tool results, preventing prompt injection.
