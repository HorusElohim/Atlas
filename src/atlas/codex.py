"""OpenAI Codex CLI lifecycle managed by Atlas."""

from __future__ import annotations

import shlex
import shutil
from pathlib import Path

from bundle.core import Entity, Process, ProcessError, ProcessResult, ProcessStream, data, logger

log = logger.get_logger(__name__)


class Codex(Entity):
    """Install, authenticate and inspect the OpenAI Codex CLI."""

    install_url: str = "https://chatgpt.com/codex/install.sh"
    home: Path = data.Field(default_factory=lambda: Path.home() / ".codex")
    system_launcher: Path = Path("/usr/local/bin/codex")

    @property
    def local_launcher(self) -> Path:
        """Return the default launcher created by the official standalone installer."""
        return Path.home() / ".local" / "bin" / "codex"

    @property
    def executable(self) -> Path | None:
        """Resolve Codex regardless of the current shell PATH."""
        if self.system_launcher.is_file():
            return self.system_launcher

        if binary := shutil.which("codex"):
            return Path(binary)

        return self.local_launcher if self.local_launcher.is_file() else None

    @property
    def installed(self) -> bool:
        """Whether a Codex CLI executable can be resolved."""
        return self.executable is not None

    async def install(self) -> Path:
        """Install Codex with OpenAI's official standalone installer when needed."""
        executable = self.executable
        if executable is not None:
            log.info("Codex is already installed at %s", executable)
            return executable

        await ProcessStream(name="Atlas.Codex.Install")(
            f"curl -fsSL {shlex.quote(self.install_url)} | sh"
        )

        if not self.local_launcher.is_file():
            raise RuntimeError(
                "Codex installer completed but ~/.local/bin/codex was not created. "
                "Check the installer output and network access."
            )

        return self.local_launcher

    async def expose(self) -> None:
        """Expose the standalone Codex launcher at /usr/local/bin/codex."""
        launcher = self.local_launcher
        if not launcher.is_file():
            # If Codex came from another supported installation method and is
            # already on PATH, there is no need to replace it.
            if self.executable is not None:
                return
            raise RuntimeError("Codex is not installed. Run `atlas codex setup` first.")

        await ProcessStream(name="Atlas.Codex.Expose")(
            "sudo install -d -m 0755 /usr/local/bin && "
            f"sudo ln -sfn {shlex.quote(str(launcher))} {shlex.quote(str(self.system_launcher))}"
        )

    async def command(self, *args: str, stream: bool = True) -> ProcessResult:
        """Run one Codex CLI command through Bundle."""
        executable = self.executable
        if executable is None:
            raise RuntimeError("Codex is not installed. Run `atlas codex setup` first.")

        command = " ".join([shlex.quote(str(executable)), *(shlex.quote(arg) for arg in args)])
        process = ProcessStream(name="Atlas.Codex") if stream else Process(name="Atlas.Codex")
        return await process(command)

    async def version(self) -> ProcessResult:
        """Print the installed Codex CLI version."""
        return await self.command("--version")

    async def login_status(self, *, stream: bool = True) -> ProcessResult:
        """Show the authentication state reported by Codex."""
        return await self.command("login", "status", stream=stream)

    async def is_logged_in(self) -> bool:
        """Return whether Codex reports a usable stored login."""
        try:
            result = await self.login_status(stream=False)
        except ProcessError:
            return False

        text = f"{result.stdout}\n{result.stderr}".strip().lower()
        return "not logged in" not in text and "logged in" in text

    async def login(self) -> ProcessResult:
        """Authenticate a headless node using Codex device-code login."""
        return await self.command("login", "--device-auth")

    async def logout(self) -> ProcessResult:
        """Remove the current Codex authentication."""
        return await self.command("logout")

    async def status(self) -> None:
        """Print version and authentication status."""
        if not self.installed:
            raise RuntimeError("Codex is not installed. Run `atlas codex setup` first.")

        await self.version()
        await self.login_status()

    async def setup(self, *, login: bool = True) -> None:
        """Install Codex and authenticate this node when requested."""
        await self.install()
        await self.expose()
        await self.version()

        if login and not await self.is_logged_in():
            log.info("Starting Codex device-code authentication.")
            await self.login()

        await self.login_status()
