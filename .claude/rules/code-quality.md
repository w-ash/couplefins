---
paths:
  - "src/**"
  - "tests/**"
---
# Code Quality Rules
- NEVER add `# type: ignore`, `# pyright: ignore`, or `# noqa` to suppress warnings — fix the root cause
- Ruff and basedpyright warnings surface real design issues — improve the architecture, don't paper over it
- `json.loads` returns `Any` — use Pydantic `TypeAdapter` to validate at boundaries
- Zero tolerance: 0 errors, 0 warnings from every tool. No exceptions.
