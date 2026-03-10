---
paths:
  - "src/**"
  - "tests/**"
---
# Code Quality Rules
- NEVER add `# type: ignore`, `# pyright: ignore`, or `# noqa` to suppress warnings — fix the root cause
- Exception: third-party stubs with genuinely wrong types (document why in a comment)
- Ruff and basedpyright warnings surface real design issues — improve the architecture, don't paper over it
- `json.loads` returns `Any` — use Pydantic `TypeAdapter` to validate at boundaries
