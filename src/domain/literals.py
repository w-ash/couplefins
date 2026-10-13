def parse_literal[S: str](raw: str, allowed: tuple[S, ...], what: str) -> S:
    """Narrow a stored string to one of the allowed literal values."""
    for value in allowed:
        if raw == value:
            return value
    raise ValueError(f"Unknown {what}: {raw!r}")
