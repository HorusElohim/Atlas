"""Hermes Agent lifecycle managed by Atlas."""

from __future__ import annotations

import shlex
import shutil
from pathlib import Path

from bundle.core import Entity, ProcessError, ProcessResult, ProcessStream, data, logger

log = logger.get_logger(__name__)


class Hermes(Entity):
    """Native Hermes Agent installation and host configuration."""

    home: Path = data.Field(default_factory=lambda: Path.home() / ".hermes")
    install_url: str = "https://hermes-agent.nousresearch.com/install.sh"
    system_launcher: Path = Path("/usr/local/bin/hermes")

    @property
    def local_launcher(self) -> Path | None:
        """Return the Hermes launcher managed by the official installer."""
        launcher = Path.home() / ".local" / "bin" / "hermes"
        if launcher.is_file():
            return launcher

        launcher = self.home / "hermes-agent" / "venv" / "bin" / "hermes"
        return launcher if launcher.is_file() else None

    @property
    def executable(self) -> Path | None:
        """Resolve Hermes regardless of the current shell PATH."""
        if self.system_launcher.is_file():
            return self.system_launcher

        if binary := shutil.which("hermes"):
            return Path(binary)

        return self.local_launcher

    @property
    def installed(self) -> bool:
        """Whether Hermes is already installed on this node."""
        return self.local_launcher is not None or self.executable is not None

    async def install(self) -> None:
        """Install Hermes natively using the official installer."""
        if self.local_launcher is not None:
            log.info("Hermes is already installed at %s", self.local_launcher)
            return

        await ProcessStream(name="Atlas.Hermes.Install")(
            f"curl -fsSL {shlex.quote(self.install_url)} | bash"
        )

        if self.local_launcher is None:
            raise RuntimeError("Hermes installer completed but the Hermes launcher was not found.")

    async def expose(self) -> None:
        """Expose Hermes system-wide at /usr/local/bin/hermes."""
        launcher = self.local_launcher
        if launcher is None:
            raise RuntimeError("Hermes is not installed; cannot expose its launcher.")

        await ProcessStream(name="Atlas.Hermes.Expose")(
            "sudo install -d -m 0755 /usr/local/bin && "
            f"sudo ln -sfn {shlex.quote(str(launcher))} {shlex.quote(str(self.system_launcher))}"
        )

    async def command(self, *args: str) -> ProcessResult:
        """Run a Hermes CLI command through Bundle."""
        executable = self.executable
        if executable is None:
            raise RuntimeError("Hermes is not installed. Run `atlas hermes setup` first.")

        command = " ".join([shlex.quote(str(executable)), *(shlex.quote(arg) for arg in args)])
        return await ProcessStream(name="Atlas.Hermes")(command)

    async def configure_native(self) -> None:
        """Give Hermes direct access to the host rather than a container backend."""
        await self.command("config", "set", "terminal.backend", "local")

    async def reconfigure(self, *, quick: bool = False) -> ProcessResult:
        """Run Hermes' own interactive setup wizard."""
        args = ["setup"]
        if quick:
            args.append("--quick")
        return await self.command(*args)

    async def doctor(self, *, strict: bool = False, fix: bool = False) -> ProcessResult:
        """Run Hermes diagnostics and optionally apply Hermes' automatic fixes."""
        args = ["doctor"]
        if fix:
            args.append("--fix")

        try:
            return await self.command(*args)
        except ProcessError as error:
            if strict:
                raise
            log.warning(
                "Hermes doctor reports incomplete configuration; "
                "optional providers and tools may remain intentionally unconfigured."
            )
            return error.result

    async def setup(self, *, quick: bool = False) -> ProcessResult:
        """Install Hermes, run its setup wizard, enforce Atlas policy, and verify it."""
        await self.install()
        await self.expose()
        await self.reconfigure(quick=quick)
        await self.configure_native()
        return await self.doctor()
