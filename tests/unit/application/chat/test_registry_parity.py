"""The chat capability parity contract, enforced.

Anything a human can do through the app, the chatbot can do for them — and
nothing more. Every use case in src/application/use_cases must be accounted
for in exactly one registry bucket: reachable from a chat tool, blacklisted
(human-only), mechanically excluded (file I/O), or internal plumbing. Adding
a use case without classifying it fails here by design.
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
    REGISTRY,
    ToolSpec,
    build_tools,
)

TOOLS = build_tools()


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
        }.items():
            stale = bucket - discovered
            assert not stale, f"Stale names in {bucket_name}: {sorted(stale)}"

    def test_buckets_are_disjoint(self) -> None:
        buckets = [
            _registry_use_cases(),
            BLACKLISTED_USE_CASES,
            MECHANICALLY_EXCLUDED_USE_CASES,
            INTERNAL_USE_CASES,
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
                kind="write",
                executor=template.executor,
                broadcast_entity=None,
            )

    def test_kind_inconsistent_with_executor_is_rejected(self) -> None:
        template = next(spec for spec in REGISTRY if spec.executor is not None)
        with pytest.raises(ValueError, match="inconsistent with executor"):
            ToolSpec(
                name=template.name,
                schema=template.schema,
                handler=template.handler,
                use_cases=template.use_cases,
                kind="read",
                executor=template.executor,
                broadcast_entity=template.broadcast_entity,
            )

    def test_handler_required_outside_agentic_kind(self) -> None:
        template = REGISTRY[0]
        with pytest.raises(ValueError, match="only agentic server tools"):
            ToolSpec(
                name=template.name,
                schema=template.schema,
                handler=None,
                use_cases=template.use_cases,
            )

    def test_single_cache_stamp_on_last_non_deferred_tool(self) -> None:
        """Deferred tools cannot carry cache_control (API 400), so the one
        breakpoint sits on the last non-deferred entry."""
        stamped = [t for t in TOOLS if "cache_control" in t]
        assert len(stamped) == 1
        assert stamped[0]["cache_control"] == {"type": "ephemeral"}
        non_deferred = [t for t in TOOLS if not t.get("defer_loading")]
        assert stamped[0] is non_deferred[-1]
        assert all("cache_control" not in t for t in TOOLS if t.get("defer_loading"))

    def test_hot_tools_load_up_front_everything_else_defers(self) -> None:
        """The hot set is pinned from observed traffic plus the agentic
        capabilities the model under-reaches for; adjust deliberately, not
        by accident — reordering or re-flagging churns the prompt cache."""
        hot = {t["name"] for t in TOOLS if not t.get("defer_loading")}
        assert hot == {
            "get_settlement_balance",
            "get_budget_overview",
            "search_transactions",
            "code_execution",
            "delegate_analysis",
            "tool_search_tool_bm25",
        }
        for tool in TOOLS:
            if tool["name"] not in hot:
                assert tool["defer_loading"] is True, tool["name"]

    def test_no_strict_schemas(self) -> None:
        """strict: true was tried and abandoned — the API caps strict tools
        at 20 per request and rejected even 16 on compiled-grammar size at
        this registry's schema complexity (both live-verified 400s). The
        boundary guard is handler validation; every schema still keeps
        additionalProperties: false and a required list. Server-tool entries
        (code_execution) have no input_schema — the API owns their shape."""
        for spec in REGISTRY:
            assert "strict" not in spec.schema, spec.name
            if "input_schema" not in spec.schema:
                assert spec.kind == "agentic", spec.name
                continue
            input_schema = spec.schema["input_schema"]
            assert isinstance(input_schema, dict)
            assert input_schema.get("additionalProperties") is False, spec.name
            assert "required" in input_schema, spec.name

    def test_no_numeric_or_array_constraints_in_schemas(self) -> None:
        """House convention: ranges belong in the property description,
        enforcement in the handler (they were unsupported under strict —
        live-verified 400 — and handler validation is the boundary now)."""
        banned = {"minimum", "maximum", "maxItems", "minItems", "multipleOf"}

        def walk(node: object, path: str) -> None:
            if isinstance(node, dict):
                overlap = banned & node.keys()
                assert not overlap, f"{path}: unsupported constraints {overlap}"
                for key, value in node.items():
                    walk(value, f"{path}.{key}")
            elif isinstance(node, list):
                for i, value in enumerate(node):
                    walk(value, f"{path}[{i}]")

        for spec in REGISTRY:
            if "input_schema" in spec.schema:
                walk(spec.schema["input_schema"], spec.name)

    def test_allowed_callers_only_on_read_tools(self) -> None:
        """Programmatic tool calling exposes read tools to the sandbox and
        nothing else: write tools stay behind two-phase confirmation and
        agentic tools stay top-level. Schema constants never carry the
        field — build_tools stamps it, so it can be switched off."""
        by_name = {t["name"]: t for t in TOOLS}
        for spec in REGISTRY:
            assert "allowed_callers" not in spec.schema, spec.name
            built = by_name[spec.name]
            if spec.kind == "read":
                assert built["allowed_callers"] == [
                    "direct",
                    "code_execution_20260120",
                ], spec.name
            else:
                assert "allowed_callers" not in built, spec.name

    def test_disabling_code_execution_removes_sandbox_surface(self) -> None:
        tool_list = build_tools(enable_code_execution=False)
        names = {t["name"] for t in tool_list}
        assert "code_execution" not in names
        assert all("allowed_callers" not in t for t in tool_list)
        assert tool_list[-1]["cache_control"] == {"type": "ephemeral"}
