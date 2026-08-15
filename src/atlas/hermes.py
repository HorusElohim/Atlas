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

    @property
    def executable(self) -> Path | None:
        """Resolve the Hermes launcher without relying on shell startup files."""
        if binary := shutil.which("hermes"):
            return Path(binary)

        launcher = self.home / "hermes-agent" / "venv" / "bin" / "hermes"
        return launcher if launcher.is_file() else None

    @property
    def installed(self) -> bool:
        return self.executable is not None

    async def install(self) -> None:
        """Install Hermes natively using the official installer."""
        if self.installed:
            log.info("Hermes is already installed at %s", self.executable)
            return

        await ProcessStream(name="Atlas.Hermes.Install")(
            f"curl -fsSL {shlex.quote(self.install_url)} | bash"
        )

        if not self.installed:
            raise RuntimeError("Hermes installer completed but the Hermes launcher was not found.")

    async def command(self, *args: str) -> ProcessResult:
        """Run a Hermes CLI command through Bundle."""
        executable = self.executable
        if executable is None:
            raise RuntimeError("Hermes is not installed. Run `atlas hermes setup` first.")

        command = " ".join([shlex.quote(str(executable)), *(shlex.quote(arg) for arg in args)])
        return await ProcessStream(name="Atlas.Hermes") (command)

    async def configure_native(self) -> None:
        """Give Hermes direct access to the host rather than a container backend."""
        await self.command("config", "set", "terminal.backend", "local")

    async def doctor(self, *, strict: bool = False) -> ProcessResult:
        """Run Hermes diagnostics; provider warnings are expected before inference exists."""
        try:
            return await self.command("doctor")
        except ProcessError as error:
            if strict:
                raise
            log.warning("Hermes doctor reports incomplete configuration; this is expected before a model provider is configured.")
            return error.result

    async def setup(self) -> ProcessResult:
        """Install Hermes and configure the native terminal backend."""
        await self.install()
        await self.configure_native()
        return await self.doctor()
