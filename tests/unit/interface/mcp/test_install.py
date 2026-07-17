"""Config-snippet generation and the install entrypoint's arg dispatch.

The emitted configs are the contract between ``install`` and ``_serve`` —
a regression here (a dropped env var, a broken shell token) registers a
server that fails every call, so the pure builders are pinned directly.
"""

import shlex
import sys

import pytest

from src.interface.mcp.__main__ import _install, main
from src.interface.mcp.install import (
    ENV_PERSON,
    SUPPORTED_CLIENTS,
    build_client_config,
    claude_code_command,
    server_entry,
)


class TestServerEntry:
    def test_carries_person_env_and_module_launch(self) -> None:
        entry = server_entry("Alice")
        assert entry["env"] == {ENV_PERSON: "Alice"}
        args = entry["args"]
        assert isinstance(args, list)
        assert args[-3:] == ["python", "-m", "src.interface.mcp"]
        assert "--directory" in args

    def test_client_config_nests_the_single_server(self) -> None:
        config = build_client_config("Alice")
        servers = config["mcpServers"]
        assert isinstance(servers, dict)
        assert set(servers) == {"couplefins"}
        assert servers["couplefins"] == server_entry("Alice")


class TestClaudeCodeCommand:
    def test_command_registers_couplefins_with_env(self) -> None:
        cmd = claude_code_command("Alice")
        assert cmd.startswith("claude mcp add couplefins")
        assert f"{ENV_PERSON}=Alice" in shlex.split(cmd)

    def test_spaced_person_name_survives_shell_splitting(self) -> None:
        """Person names allow spaces (setup validates non-empty only) — the
        env assignment must stay one argv token or the registered server
        sees a truncated name and fails every call."""
        tokens = shlex.split(claude_code_command("Mary Ann"))
        assert f"{ENV_PERSON}=Mary Ann" in tokens


class TestInstallDispatch:
    def test_client_key_alone_takes_person_from_env(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`install cursor` means client=cursor — a client key must never be
        silently embedded as the acting person."""
        monkeypatch.setenv(ENV_PERSON, "Alice")
        _install(["cursor"])
        out = capsys.readouterr().out
        assert f'"{ENV_PERSON}": "Alice"' in out

    def test_client_key_alone_without_env_errors(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.delenv(ENV_PERSON, raising=False)
        with pytest.raises(SystemExit):
            _install(["cursor"])

    def test_client_then_person_positional_form(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`install cursor Alice` must register Alice — never silently fall
        back to whatever the env var happens to hold."""
        monkeypatch.setenv(ENV_PERSON, "Bob")
        _install(["cursor", "Alice"])
        out = capsys.readouterr().out
        assert f'"{ENV_PERSON}": "Alice"' in out

    def test_person_then_client_positional_form(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.delenv(ENV_PERSON, raising=False)
        _install(["Alice", "cursor"])
        out = capsys.readouterr().out
        assert f'"{ENV_PERSON}": "Alice"' in out

    def test_unknown_client_errors(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.delenv(ENV_PERSON, raising=False)
        with pytest.raises(SystemExit):
            _install(["Alice", "not-a-client"])

    def test_every_supported_client_produces_output(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        for client in SUPPORTED_CLIENTS:
            _install(["Alice", client])
            assert capsys.readouterr().out.strip()


class TestMainDispatch:
    def test_unknown_command_errors_instead_of_serving(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A typo'd subcommand must not fall through to the stdio server,
        which would block forever waiting for JSON-RPC on stdin."""
        monkeypatch.setattr(sys, "argv", ["prog", "instal", "cursor"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 2
        assert "Unknown command" in capsys.readouterr().err
