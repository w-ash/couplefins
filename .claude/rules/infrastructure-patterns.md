---
paths:
  - "src/infrastructure/**"
---
# Infrastructure Layer Rules
- NEVER expose ORM models to application/domain — convert via `_to_domain()` / `_to_model()`
- All repository methods have batch variants (`save_batch`)
- `models/__init__.py` is the canonical import point — all models register with `Base.metadata` there
