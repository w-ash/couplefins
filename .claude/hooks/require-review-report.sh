#!/bin/bash
# Stop hook for reviewer agents.
# Blocks the agent from stopping until it produces a structured report
# containing "### Verdict:". Prevents infinite loops via stop_hook_active.

INPUT=$(cat)

# Defensive: if we can't parse JSON, let the agent stop
if ! echo "$INPUT" | jq empty 2>/dev/null; then
  exit 0
fi

STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false')
LAST_MSG=$(echo "$INPUT" | jq -r '.last_assistant_message // ""')

# If the hook already forced a continuation, don't loop — let it stop
if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
  exit 0
fi

# Check if the report format is present
if echo "$LAST_MSG" | grep -q '### Verdict:'; then
  exit 0
fi

# No report found — block the stop and force the agent to write one
echo "STOP reading files. You have used all your investigation turns. You MUST now write your final report using the structured format ending with '### Verdict: APPROVED | APPROVED WITH SUGGESTIONS | REJECTED'. If you found no issues, report APPROVED. Do NOT read any more files." >&2
exit 2
