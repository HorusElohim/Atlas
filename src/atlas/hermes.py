"""Hermes Agent lifecycle managed by Atlas."""

from __future__ import annotations

import asyncio
import shlex
import shutil
import urllib.error
import urllib.request
from pathlib import Path

import yaml
from bundle.core import Entity, ProcessError, ProcessResult, ProcessStream, data, logger

log = logger.get_logger(__name__)


class Hermes(Entity):
    """Native Hermes Agent installation and host configuration."""

    home: Path = data.Field(default_factory=lambda: Path.home() / ".hermes")
    install_url: str = "https://hermes-agent.nousresearch.com/install.sh"
    system_launcher: Path = Path("/usr/local/bin/hermes")
    atlas_provider_name: str = "atlas"
    atlas_key_env: str = "ATLAS_INFERENCE_API_KEY"

    @property
    def config_file(self) -> Path:
        return self.home / "config.yaml"

    @property
    def env_file(self) -> Path:
        return self.home / ".env"

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

    async def connect(
        self,
        base_url: str,
        api_key: str,
        *,
        model: str = "Qwen3.8-27B",
        context: int = 65_536,
    ) -> None:
        """Connect Hermes to the authenticated Atlas OpenAI-compatible inference endpoint."""
        if context < 64_000:
            raise ValueError("Hermes requires at least 64000 tokens of context.")

        normalized_url = base_url.rstrip("/")
        if not normalized_url.endswith("/v1"):
            normalized_url += "/v1"

        await asyncio.to_thread(self._verify_inference_endpoint, normalized_url, api_key)
        self._configure_atlas_provider(normalized_url, api_key, model=model, context=context)
        await self.configure_native()

        log.info("Hermes provider configured: custom:%s", self.atlas_provider_name)
        log.info("Model: %s (%s tokens)", model, context)
        log.info("Endpoint: %s", normalized_url)

    def _verify_inference_endpoint(self, base_url: str, api_key: str) -> None:
        """Verify the remote llama.cpp OpenAI-compatible model endpoint without logging its key."""
        request = urllib.request.Request(
            f"{base_url}/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                if response.status != 200:
                    raise RuntimeError(f"Inference endpoint returned HTTP {response.status}.")
        except (urllib.error.URLError, TimeoutError) as error:
            raise RuntimeError(f"Cannot reach Atlas inference endpoint at {base_url}.") from error

    def _configure_atlas_provider(self, base_url: str, api_key: str, *, model: str, context: int) -> None:
        """Persist Atlas as a named Hermes custom provider while preserving unrelated settings."""
        self.home.mkdir(parents=True, exist_ok=True)

        config: dict = {}
        if self.config_file.is_file():
            loaded = yaml.safe_load(self.config_file.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                config = loaded

        providers = config.get("providers")
        if not isinstance(providers, dict):
            providers = {}

        provider = providers.get(self.atlas_provider_name)
        if not isinstance(provider, dict):
            provider = {}

        models = provider.get("models")
        if not isinstance(models, dict):
            models = {}

        model_settings = models.get(model)
        if not isinstance(model_settings, dict):
            model_settings = {}
        model_settings["context_length"] = context
        models[model] = model_settings

        provider.update(
            {
                "api": base_url,
                "key_env": self.atlas_key_env,
                "transport": "chat_completions",
                "default_model": model,
                "models": models,
            }
        )
        providers[self.atlas_provider_name] = provider
        config["providers"] = providers

        model_config = config.get("model")
        if not isinstance(model_config, dict):
            model_config = {}
        model_config.update(
            {
                "default": model,
                "provider": f"custom:{self.atlas_provider_name}",
            }
        )
        for stale_key in ("base_url", "api_key", "api_mode", "context_length"):
            model_config.pop(stale_key, None)
        config["model"] = model_config

        self.config_file.write_text(
            yaml.safe_dump(config, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        self._set_env_secret(self.atlas_key_env, api_key)

    def _set_env_secret(self, key: str, value: str) -> None:
        """Set one Hermes .env secret without replacing unrelated entries."""
        lines = self.env_file.read_text(encoding="utf-8").splitlines() if self.env_file.is_file() else []
        prefix = f"{key}="
        replacement = f"{prefix}{value}"
        output: list[str] = []
        replaced = False

        for line in lines:
            if line.startswith(prefix):
                if not replaced:
                    output.append(replacement)
                    replaced = True
                continue
            output.append(line)

        if not replaced:
            output.append(replacement)

        self.env_file.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
        self.env_file.chmod(0o600)

    async def setup(self, *, quick: bool = False) -> ProcessResult:
        """Install Hermes, run its setup wizard, enforce Atlas policy, and verify it."""
        await self.install()
        await self.expose()
        await self.reconfigure(quick=quick)
        await self.configure_native()
        return await self.doctor()
