"""End-to-end validation for Atlas inference and Hermes integration."""

from __future__ import annotations

import asyncio
import json
import shlex
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import yaml
from bundle.core import Entity, Process, ProcessError, logger

from .hermes import Hermes
from .inference import Inference

log = logger.get_logger(__name__)


class Validation(Entity):
    """Validate Atlas services from engine to Hermes agent response."""

    async def inference(
        self,
        inference: Inference,
        *,
        host: str = "127.0.0.1",
        port: int = 8_080,
        model: str | None = None,
    ) -> None:
        """Validate systemd, HTTP reachability, model discovery and one real completion."""
        if not inference.unit_file.is_file():
            raise RuntimeError(
                "Atlas inference service is not installed. Run `atlas inference qwen setup` first."
            )

        try:
            await Process(name="Atlas.Validation.Inference.Service")(
                f"systemctl is-active --quiet {shlex.quote(inference.service_name)}"
            )
        except ProcessError as error:
            raise RuntimeError(
                "atlas-inference.service is installed but is not active. Run `atlas inference status`."
            ) from error
        log.info("✓ Service active: %s", inference.service_name)

        if not inference.api_key_file.is_file():
            raise RuntimeError(f"Inference API key is missing: {inference.api_key_file}")
        api_key = inference.api_key_file.read_text(encoding="utf-8").strip()
        if not api_key:
            raise RuntimeError(f"Inference API key is empty: {inference.api_key_file}")

        base_url = f"http://{host}:{port}/v1"
        selected_model = model or inference.model_alias

        await asyncio.to_thread(self._request_json, f"http://{host}:{port}/health", api_key)
        log.info("✓ HTTP health reachable: http://%s:%s/health", host, port)

        models = await asyncio.to_thread(self._request_json, f"{base_url}/models", api_key)
        model_ids = self._model_ids(models)
        if selected_model not in model_ids:
            raise RuntimeError(
                f"Inference endpoint is reachable but model {selected_model!r} is not advertised; "
                f"available models: {', '.join(model_ids) or '<none>'}."
            )
        log.info("✓ Model advertised: %s", selected_model)

        reply = await asyncio.to_thread(
            self._completion,
            base_url,
            api_key,
            selected_model,
            "Reply with exactly ATLAS_QWEN_OK and nothing else.",
        )
        if not reply:
            raise RuntimeError("Qwen returned an empty completion.")
        log.info("✓ Qwen completion works: %s", self._preview(reply))

    async def hermes(self, hermes: Hermes) -> None:
        """Validate Hermes config, configured endpoint reachability and one Hermes one-shot response."""
        if not hermes.installed:
            raise RuntimeError("Hermes is not installed. Run `atlas hermes setup` first.")

        base_url, api_key, model = self._configured_hermes_target(hermes)
        log.info("✓ Hermes provider configured: custom:%s", hermes.atlas_provider_name)
        log.info("✓ Hermes model configured: %s", model)

        models = await asyncio.to_thread(self._request_json, f"{base_url}/models", api_key)
        model_ids = self._model_ids(models)
        if model not in model_ids:
            raise RuntimeError(
                f"Hermes endpoint {base_url} is reachable but does not advertise {model!r}; "
                f"available models: {', '.join(model_ids) or '<none>'}."
            )
        log.info("✓ Hermes endpoint reachable: %s", base_url)

        executable = hermes.executable
        if executable is None:
            raise RuntimeError("Hermes launcher could not be resolved.")

        prompt = "Reply with exactly HERMES_ATLAS_OK and nothing else. Do not use tools."
        command = f"{shlex.quote(str(executable))} -z {shlex.quote(prompt)}"
        try:
            result = await Process(name="Atlas.Validation.Hermes.OneShot")(command)
        except ProcessError as error:
            raise RuntimeError(
                "Hermes could not complete a one-shot request through its configured Atlas provider."
            ) from error

        reply = result.stdout.strip()
        if not reply:
            raise RuntimeError("Hermes completed without returning a response.")
        log.info("✓ Hermes → Qwen end-to-end works: %s", self._preview(reply))

    def _configured_hermes_target(self, hermes: Hermes) -> tuple[str, str, str]:
        """Resolve the Atlas provider selected by Hermes without exposing its secret."""
        if not hermes.config_file.is_file():
            raise RuntimeError(f"Hermes config is missing: {hermes.config_file}")

        loaded = yaml.safe_load(hermes.config_file.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise RuntimeError(f"Hermes config is invalid: {hermes.config_file}")

        model_config = loaded.get("model")
        if not isinstance(model_config, dict):
            raise RuntimeError("Hermes model configuration is missing.")

        expected_provider = f"custom:{hermes.atlas_provider_name}"
        if model_config.get("provider") != expected_provider:
            raise RuntimeError(
                f"Hermes is not pointed at Atlas; expected model.provider={expected_provider!r}, "
                f"got {model_config.get('provider')!r}. Run `atlas hermes connect-local` or `atlas hermes connect`."
            )

        model = model_config.get("default") or model_config.get("model")
        if not isinstance(model, str) or not model:
            raise RuntimeError("Hermes Atlas model is not configured.")

        providers = loaded.get("providers")
        if not isinstance(providers, dict):
            raise RuntimeError("Hermes named providers configuration is missing.")
        provider = providers.get(hermes.atlas_provider_name)
        if not isinstance(provider, dict):
            raise RuntimeError(f"Hermes provider {hermes.atlas_provider_name!r} is missing.")

        base_url = provider.get("api") or provider.get("base_url") or provider.get("url")
        if not isinstance(base_url, str) or not base_url:
            raise RuntimeError("Hermes Atlas provider has no API URL.")
        base_url = base_url.rstrip("/")
        if not base_url.endswith("/v1"):
            base_url += "/v1"

        key_env = provider.get("key_env")
        if not isinstance(key_env, str) or not key_env:
            raise RuntimeError("Hermes Atlas provider has no key_env configured.")
        api_key = self._read_env(hermes.env_file, key_env)
        if not api_key:
            raise RuntimeError(f"Hermes secret {key_env} is missing from {hermes.env_file}.")

        return base_url, api_key, model

    @staticmethod
    def _read_env(path: Path, key: str) -> str | None:
        """Read one simple KEY=value entry from an env file."""
        if not path.is_file():
            return None
        prefix = f"{key}="
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith(prefix):
                return line[len(prefix):].strip()
        return None

    @staticmethod
    def _model_ids(payload: Any) -> list[str]:
        """Extract model IDs from an OpenAI-compatible /v1/models response."""
        if not isinstance(payload, dict):
            return []
        data = payload.get("data")
        if not isinstance(data, list):
            return []
        return [item["id"] for item in data if isinstance(item, dict) and isinstance(item.get("id"), str)]

    def _completion(self, base_url: str, api_key: str, model: str, prompt: str) -> str:
        """Run one small OpenAI-compatible chat completion and extract returned text."""
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 64,
        }
        response = self._request_json(
            f"{base_url}/chat/completions",
            api_key,
            method="POST",
            payload=payload,
            timeout=180,
        )
        if not isinstance(response, dict):
            return ""
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        choice = choices[0]
        if not isinstance(choice, dict):
            return ""
        message = choice.get("message")
        if not isinstance(message, dict):
            return ""

        parts = []
        for key in ("content", "reasoning_content"):
            value = message.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(value.strip())
        return "\n".join(parts)

    @staticmethod
    def _request_json(
        url: str,
        api_key: str,
        *,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
        timeout: int = 30,
    ) -> Any:
        """Perform one authenticated JSON request with actionable errors."""
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        if data is not None:
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{method} {url} returned HTTP {error.code}: {body[:500]}") from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise RuntimeError(f"Cannot reach {url}: {error}") from error

        if not body.strip():
            return {}
        try:
            return json.loads(body)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"{method} {url} returned invalid JSON: {body[:500]}") from error

    @staticmethod
    def _preview(text: str, limit: int = 160) -> str:
        """Return a compact single-line response preview for validation logs."""
        compact = " ".join(text.split())
        return compact if len(compact) <= limit else compact[: limit - 1] + "…"
