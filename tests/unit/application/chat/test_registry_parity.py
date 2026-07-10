"""The chat capability parity contract, enforced.

Anything a human can do through the app, the chatbot can do for them — and
nothing more. Every use case in src/application/use_cases must be accounted
for in exactly one registry bucket: reachable from a chat tool, blacklisted
(human-only), mechanically excluded (file I/O), internal plumbing, or pending
a scheduled parity phase. Adding a use case without classifying it fails here
by design.
"""

import importlib
import inspect
import pkgutil

import pytest

from src.application import use_cases as use_cases_pkg
from src.application.chat.registry import (
    BLACKLISTED_USE_CASES,
    INTERNAL_USE_CASES,
    MECHANICALLY_EXCLUDED_USE_CASES,
    PENDING_PARITY_USE_CASES,
    REGISTRY,
    TOOLS,
    ToolSpec,
)


def _discover_use_cases() -> set[str]:
    """Every use case name in src/application/use_cases (recursively).

    Collects classes named *UseCase, plus public module-level async functions
    in modules that define no UseCase class (function-style use cases like
    list_budgets). _shared helpers are excluded — they are building blocks,
    not capabilities.
    """
    names: set[str] = set()
    for module_info in pkgutil.walk_packages(
        use_cases_pkg.__path__, prefix=f"{use_cases_pkg.__name__}."
    ):
        short_name = module_info.name.removeprefix(f"{use_cases_pkg.__name__}.")
        if short_name.startswith("_shared") or short_name.endswith("__init__"):
            continue
        module = importlib.import_module(module_info.name)
        classes = [
            name
            for name, obj in inspect.getmembers(module, inspect.isclass)
            if name.endswith("UseCase") and obj.__module__ == module_info.name
        ]
        if classes:
            names.update(classes)
            continue
        names.update(
            name
            for name, obj in inspect.getmembers(module, inspect.iscoroutinefunction)
            if not name.startswith("_") and obj.__module__ == module_info.name
        )
    return names


def _registry_use_cases() -> set[str]:
    return {uc for spec in REGISTRY for uc in spec.use_cases}


class TestParityContract:
    def test_every_use_case_is_classified(self) -> None:
        discovered = _discover_use_cases()
        classified = (
            _registry_use_cases()
            | BLACKLISTED_USE_CASES
            | MECHANICALLY_EXCLUDED_USE_CASES
            | INTERNAL_USE_CASES
            | PENDING_PARITY_USE_CASES
        )
        unclassified = discovered - classified
        assert not unclassified, (
            f"Use cases not reachable from chat and not explicitly excluded: "
            f"{sorted(unclassified)}. Add a chat tool to the registry, or "
            f"classify them in src/application/chat/registry.py."
        )

    def test_no_stale_classifications(self) -> None:
        """Every classified name must still exist — catches renames/removals."""
        discovered = _discover_use_cases()
        for bucket_name, bucket in {
            "registry": _registry_use_cases(),
            "blacklist": BLACKLISTED_USE_CASES,
            "mechanical": MECHANICALLY_EXCLUDED_USE_CASES,
            "internal": INTERNAL_USE_CASES,
            "pending": PENDING_PARITY_USE_CASES,
        }.items():
            stale = bucket - discovered
            assert not stale, f"Stale names in {bucket_name}: {sorted(stale)}"

    def test_buckets_are_disjoint(self) -> None:
        buckets = [
            _registry_use_cases(),
            BLACKLISTED_USE_CASES,
            MECHANICALLY_EXCLUDED_USE_CASES,
            INTERNAL_USE_CASES,
            PENDING_PARITY_USE_CASES,
        ]
        for i, a in enumerate(buckets):
            for b in buckets[i + 1 :]:
                overlap = a & b
                assert not overlap, f"Use cases in two buckets: {sorted(overlap)}"

    def test_no_blacklisted_use_case_is_chat_reachable(self) -> None:
        reachable = _registry_use_cases()
        violations = reachable & BLACKLISTED_USE_CASES
        assert not violations, (
            f"Blacklisted (human-only) use cases exposed to chat: {sorted(violations)}"
        )


class TestRegistryShape:
    def test_mismatched_schema_name_is_rejected(self) -> None:
        template = REGISTRY[0]
        with pytest.raises(ValueError, match="bound to schema"):
            ToolSpec(
                name="not_the_schema_name",
                schema=template.schema,
                handler=template.handler,
                use_cases=template.use_cases,
            )

    def test_executor_without_broadcast_is_rejected(self) -> None:
        template = next(spec for spec in REGISTRY if spec.executor is not None)
        with pytest.raises(ValueError, match="must be set together"):
            ToolSpec(
                name=template.name,
                schema=template.schema,
                handler=template.handler,
                use_cases=template.use_cases,
                executor=template.executor,
                broadcast_entity=None,
            )

    def test_only_last_tool_carries_cache_control(self) -> None:
        assert all("cache_control" not in t for t in TOOLS[:-1])
        assert TOOLS[-1]["cache_control"] == {"type": "ephemeral"}
