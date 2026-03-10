---
paths:
  - "tests/**"
---
# Test Rules
- Test level by source layer: domain=unit, use case=unit+mock UoW, repository=integration, routes=integration
- Use factory functions from `tests/fixtures/factories.py` — don't construct entities inline
- Use `make_mock_uow()` from `tests/fixtures/mocks.py` for use case tests
- Markers auto-applied by directory — never add `@pytest.mark.unit` manually
