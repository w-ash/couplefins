"""The registry → MCP metadata bridge: annotations, exposure, schema shaping.

Pure functions over the shared REGISTRY tuple — no SDK transport, no DB.
These lock the derivations: annotations from ``kind``, the exposed-set
filter, and the confirm-field augmentation on write schemas.
"""

from src.application.chat.registry import REGISTRY
from src.interface.mcp.exposure import mcp_exposure
from src.interface.mcp.server import (
    _CONFIRM_PROPERTIES,
    _to_mcp_tool,
    exposed_specs,
    mcp_annotations,
)


class TestAnnotations:
    def test_read_tool_is_readonly_idempotent_closed_world(self) -> None:
        spec = next(s for s in REGISTRY if s.kind == "read")
        ann = mcp_annotations(spec)
        assert ann.read_only_hint is True
        assert ann.destructive_hint is False
        assert ann.idempotent_hint is True
        assert ann.open_world_hint is False

    def test_write_tool_is_destructive_not_readonly(self) -> None:
        spec = next(s for s in REGISTRY if s.kind == "write")
        ann = mcp_annotations(spec)
        assert ann.read_only_hint is False
        assert ann.destructive_hint is True
        assert ann.idempotent_hint is False
        assert ann.open_world_hint is False

    def test_every_exposed_tool_has_derivable_annotations(self) -> None:
        # No exception, and read/write hints are mutually exclusive per tool.
        for spec in exposed_specs():
            ann = mcp_annotations(spec)
            assert ann.read_only_hint is not ann.destructive_hint


class TestExposure:
    def test_every_registry_tool_is_classified(self) -> None:
        for spec in REGISTRY:
            assert mcp_exposure(spec) in {"exposed", "agentic"}

    def test_reads_and_writes_exposed(self) -> None:
        read = next(s for s in REGISTRY if s.kind == "read")
        write = next(s for s in REGISTRY if s.kind == "write")
        assert mcp_exposure(read) == "exposed"
        assert mcp_exposure(write) == "exposed"

    def test_exposed_specs_excludes_agentic(self) -> None:
        names = {s.name for s in exposed_specs()}
        assert "code_execution" not in names
        assert "delegate_analysis" not in names
        assert "tool_search_tool_bm25" not in names
        # And it is exactly the 'exposed' partition of the registry.
        assert names == {s.name for s in REGISTRY if mcp_exposure(s) == "exposed"}

    def test_exposed_set_is_nonempty_with_reads_and_writes(self) -> None:
        kinds = {s.kind for s in exposed_specs()}
        assert kinds == {"read", "write"}


class TestSchemaAugmentation:
    def test_write_schema_gains_confirm_fields(self) -> None:
        spec = next(s for s in REGISTRY if s.kind == "write")
        tool = _to_mcp_tool(spec)
        props = tool.input_schema.get("properties", {})
        assert "confirm" in props
        assert "confirm_token" in props
        # Original properties are preserved alongside the injected ones.
        original_schema = dict(spec.schema)["input_schema"]
        assert isinstance(original_schema, dict)
        for original_key in original_schema.get("properties", {}):
            assert original_key in props

    def test_read_schema_untouched(self) -> None:
        spec = next(s for s in REGISTRY if s.kind == "read")
        tool = _to_mcp_tool(spec)
        props = tool.input_schema.get("properties", {})
        assert "confirm" not in props
        assert "confirm_token" not in props

    def test_confirm_properties_are_declared(self) -> None:
        assert set(_CONFIRM_PROPERTIES) == {"confirm", "confirm_token"}

    def test_no_write_tool_claims_the_reserved_field_names(self) -> None:
        """properties.update(_CONFIRM_PROPERTIES) would silently replace a
        real property of the same name and handle_write_call would consume
        its value — the import-time guard enforces this; assert it here so
        the reservation is a named contract."""
        for spec in exposed_specs():
            if spec.kind != "write":
                continue
            schema = dict(spec.schema)["input_schema"]
            assert isinstance(schema, dict)
            props = schema.get("properties", {})
            assert isinstance(props, dict)
            assert not set(_CONFIRM_PROPERTIES) & set(props), spec.name
