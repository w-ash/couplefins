---
paths:
  - "src/domain/**"
---
# Domain Layer Rules
- NEVER import from infrastructure, application, or interface layers
- Entities are frozen attrs classes (`@define(frozen=True, slots=True)`)
- Repository interfaces are Protocol classes only — zero implementation
- Parsing functions are pure: no I/O, no side effects, only stdlib + domain imports
