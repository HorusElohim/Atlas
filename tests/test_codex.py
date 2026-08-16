from pathlib import Path

import pytest
from bundle.core import ProcessResult

from atlas.codex import Codex


def make_codex(tmp_path: Path) -> Codex:
    return Codex(
        name="TestCodex",
        home=tmp_path / ".codex",
        bin_dir=tmp_path / ".local" / "bin",
        system_launcher=tmp_path / "usr" / "local" / "bin" / "codex",
    )


def test_local_launcher_uses_managed_bin_dir(tmp_path: Path) -> None:
    codex = make_codex(tmp_path)

    assert codex.local_launcher == tmp_path / ".local" / "bin" / "codex"


def test_executable_falls_back_to_standalone_launcher(tmp_path: Path, monkeypatch) -> None:
    codex = make_codex(tmp_path)
    codex.local_launcher.parent.mkdir(parents=True)
    codex.local_launcher.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr("atlas.codex.shutil.which", lambda _: None)

    assert codex.executable == codex.local_launcher
    assert codex.installed


def test_login_status_detection() -> None:
    logged_in = ProcessResult(
        command="codex login status",
        returncode=0,
        stdout="Logged in using ChatGPT\n",
        stderr="",
    )
    logged_out = ProcessResult(
        command="codex login status",
        returncode=1,
        stdout="Not logged in\n",
        stderr="",
    )

    assert "logged in" in Codex._login_status_text(logged_in)
    assert "not logged in" in Codex._login_status_text(logged_out)


@pytest.mark.asyncio
async def test_show_version_is_bound_and_invokes_codex(tmp_path: Path, monkeypatch) -> None:
    codex = make_codex(tmp_path)
    expected = ProcessResult(
        command="codex --version",
        returncode=0,
        stdout="codex-cli test\n",
        stderr="",
    )
    calls: list[tuple[str, ...]] = []

    async def fake_command(*args: str, stream: bool = True) -> ProcessResult:
        calls.append(args)
        return expected

    monkeypatch.setattr(codex, "command", fake_command)

    result = await codex.show_version()

    assert result == expected
    assert calls == [("--version",)]
