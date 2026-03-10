---
paths:
  - "src/application/**"
---
# Application Layer Rules
- `runner.py` is the composition root — it wires infrastructure to domain (top-level infra imports are correct here)
- Use cases receive `UnitOfWorkProtocol` as a parameter — NEVER import infrastructure
- Use case owns transaction boundaries (commit/rollback)
- All use cases run through `execute_use_case()`
