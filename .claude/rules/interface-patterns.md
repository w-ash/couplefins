---
paths:
  - "src/interface/**"
---
# Interface Layer Rules
- NEVER access repositories directly — call execute_use_case()
- Zero business logic in route handlers — delegate to use cases
- Route handlers are 5-10 lines maximum
