"""Atlas command-line interface."""

from __future__ import annotations

import asyncio
import json
import shlex
from pathlib import Path

import rich_click as click
from bundle.core import Process, ProcessError, ProcessStream

from .hardware import Hardware
from .hermes import Hermes
from .inference import Inference
from .ohmyzsh import OhMyZsh
from .validation import Validation


def _run_cli(coroutine) -> None:
    """Run one async Atlas operation and present expected failures as CLI errors."""
    try:
        asyncio.run(coroutine)
    except (RuntimeError, ValueError) as error:
        raise click.ClickException(str(error)) from error


async def _apply_inference_networking(
    inference: Inference,
    *,
    host: str,
    port: int,
    public_access: bool = False,
) -> None:
    """Restart inference after unit changes and optionally expose its port through UFW."""
    try:
        await ProcessStream(name="Atlas.Inference.Systemd.Restart")(
            f"sudo systemctl restart {shlex.quote(inference.service_name)}"
        )
    except ProcessError as error:
        raise RuntimeError(
            "Atlas wrote the inference service configuration but could not restart it. "
            "Run `atlas inference status` for details."
        ) from error

    await inference.wait_ready(host=host, port=port)

    if not public_access:
        return

    try:
        await Process(name="Atlas.Inference.Ufw.Detect")("command -v ufw")
    except ProcessError:
        click.echo("✓ UFW is not installed; no host firewall rule is required")
        return

    try:
        status = await Process(name="Atlas.Inference.Ufw.Status")("sudo ufw status")
    except ProcessError as error:
        raise RuntimeError("UFW is installed but Atlas could not read its status.") from error

    if "Status: active" not in status.stdout:
        click.echo("✓ UFW is installed but inactive; no firewall rule is required")
        return

    try:
        await ProcessStream(name="Atlas.Inference.Ufw.Allow")(
            f"sudo ufw allow {port}/tcp"
        )
    except ProcessError as error:
        raise RuntimeError(f"Could not allow public TCP port {port} through UFW.") from error

    click.echo(f"✓ UFW allows TCP {port} from any source")


@click.group()
def main() -> None:
    """Orchestrate a distributed Hermes agent fleet."""


@main.command()
def inspect() -> None:
    """Inspect this machine and print Atlas-relevant capabilities."""
    hardware = asyncio.run(Hardware.inspect())
    payload = hardware.model_dump(mode="json")
    payload["capabilities"] = {
        "hermes": True,
        "jetson": hardware.is_jetson,
        "qwen_27b": hardware.can_run_qwen_27b,
    }
    click.echo(json.dumps(payload, indent=2))


@main.command(name="validate")
@click.option("--host", default="127.0.0.1", show_default=True, help="Reachable local inference address to test.")
@click.option("--port", default=8_080, show_default=True, type=int, help="Local inference port to test.")
def validate(host: str, port: int) -> None:
    """Validate this node's Qwen service and Hermes integration end-to-end."""

    async def run() -> None:
        validation = Validation(name="Validation")
        await validation.inference(Inference(name="Inference"), host=host, port=port)
        await validation.hermes(Hermes(name="Hermes"))

    _run_cli(run())


@main.group(name="hermes")
def hermes_cli() -> None:
    """Manage the Hermes Agent installation on this node."""


@hermes_cli.command(name="setup")
@click.option("--quick", is_flag=True, help="Only prompt for missing or unset Hermes settings.")
def hermes_setup(quick: bool) -> None:
    """Install Hermes, run its setup wizard, enforce native execution, and verify it."""
    asyncio.run(Hermes(name="Hermes").setup(quick=quick))


@hermes_cli.command(name="expose")
def hermes_expose() -> None:
    """Expose the Hermes launcher at /usr/local/bin/hermes."""
    asyncio.run(Hermes(name="Hermes").expose())


@hermes_cli.command(name="connect")
@click.argument("base_url")
@click.option("--model", default="Qwen3.8-27B", show_default=True, help="Model alias exposed by Atlas inference.")
@click.option("--context", default=65_536, show_default=True, type=int, help="Configured model context window.")
@click.option(
    "--api-key-file",
    type=click.Path(path_type=Path, dir_okay=False, readable=True),
    help="Read the Atlas inference API key from a file.",
)
@click.option(
    "--api-key",
    envvar="ATLAS_INFERENCE_API_KEY",
    help="Inference API key. Prefer --api-key-file or ATLAS_INFERENCE_API_KEY.",
)
def hermes_connect(
    base_url: str,
    model: str,
    context: int,
    api_key_file: Path | None,
    api_key: str | None,
) -> None:
    """Connect Hermes to an Atlas OpenAI-compatible inference endpoint."""
    if api_key_file is not None and api_key is not None:
        raise click.UsageError("Use either --api-key-file or --api-key, not both.")

    if api_key_file is not None:
        api_key = api_key_file.read_text(encoding="utf-8").strip()
    elif api_key is None:
        api_key = click.prompt("Inference API key", hide_input=True).strip()

    if not api_key:
        raise click.UsageError("An inference API key is required.")

    _run_cli(
        Hermes(name="Hermes").connect(
            base_url,
            api_key,
            model=model,
            context=context,
        )
    )


@hermes_cli.command(name="connect-local")
@click.option("--port", default=8_080, show_default=True, type=int, help="Local Atlas inference port.")
@click.option("--model", default="Qwen3.8-27B", show_default=True, help="Local model alias.")
@click.option("--context", default=65_536, show_default=True, type=int, help="Configured model context window.")
def hermes_connect_local(port: int, model: str, context: int) -> None:
    """Validate and point Hermes at the Atlas inference service on this machine."""
    inference = Inference(name="Inference")
    if not inference.api_key_file.is_file():
        raise click.ClickException(
            "Atlas inference API key does not exist yet. Run `atlas inference qwen setup` first."
        )

    api_key = inference.api_key_file.read_text(encoding="utf-8").strip()
    if not api_key:
        raise click.ClickException(f"Atlas inference API key is empty: {inference.api_key_file}")

    async def run() -> None:
        # Do not mutate Hermes until the local service and model have proven that
        # they can answer a real OpenAI-compatible completion.
        await Validation(name="Validation").inference(
            inference,
            host="127.0.0.1",
            port=port,
            model=model,
        )
        await Hermes(name="Hermes").connect(
            f"http://127.0.0.1:{port}/v1",
            api_key,
            model=model,
            context=context,
        )

    _run_cli(run())


@hermes_cli.command(name="validate")
def hermes_validate() -> None:
    """Validate Hermes configuration, endpoint reachability and a real one-shot model response."""
    _run_cli(Validation(name="Validation").hermes(Hermes(name="Hermes")))


@hermes_cli.command(name="doctor")
@click.option("--fix", is_flag=True, help="Apply Hermes automatic configuration and state fixes.")
@click.option("--strict", is_flag=True, help="Fail when Hermes reports an incomplete configuration.")
def hermes_doctor(fix: bool, strict: bool) -> None:
    """Run Hermes diagnostics."""
    asyncio.run(Hermes(name="Hermes").doctor(strict=strict, fix=fix))


@main.group(name="inference")
def inference_cli() -> None:
    """Manage the CUDA llama.cpp inference service on a GPU node."""


@inference_cli.command(name="setup")
@click.option(
    "--hf-repo",
    default=None,
    help="Verified Hugging Face GGUF repository to deploy. Omit to build the CUDA engine only.",
)
@click.option("--quant", default="Q4_K_M", show_default=True, help="GGUF quantization tag.")
@click.option("--context", default=65_536, show_default=True, type=int, help="Server context size in tokens.")
@click.option("--host", default="127.0.0.1", show_default=True, help="Inference listen address.")
@click.option("--port", default=8_080, show_default=True, type=int, help="Inference listen port.")
def inference_setup(hf_repo: str | None, quant: str, context: int, host: str, port: int) -> None:
    """Build pinned CUDA llama.cpp and optionally deploy an authenticated GGUF model service."""
    asyncio.run(
        Inference(name="Inference").setup(
            hf_repo=hf_repo,
            quant=quant,
            context=context,
            host=host,
            port=port,
        )
    )


@inference_cli.group(name="qwen")
def inference_qwen_cli() -> None:
    """Manage the Atlas Qwen3.8-27B model profile."""


@inference_qwen_cli.command(name="setup")
@click.option("--quant", default="Q4_K_M", show_default=True, help="GGUF quantization to build.")
@click.option("--context", default=65_536, show_default=True, type=int, help="Server context size in tokens.")
@click.option("--host", default="127.0.0.1", show_default=True, help="Inference listen address when --public is not used.")
@click.option("--port", default=8_080, show_default=True, type=int, help="Inference listen port.")
@click.option("--public", "public_access", is_flag=True, help="Listen on all IPv4 interfaces and allow this TCP port from any source through active UFW.")
@click.option("--keep-bf16", is_flag=True, help="Keep the large intermediate BF16 GGUF after quantization.")
def inference_qwen_setup(
    quant: str,
    context: int,
    host: str,
    port: int,
    public_access: bool,
    keep_bf16: bool,
) -> None:
    """Convert, quantize and serve Qwen3.8-27B from its official Hugging Face checkpoint."""
    effective_host = "0.0.0.0" if public_access else host

    async def run() -> None:
        inference = Inference(name="Inference")
        await inference.qwen_setup(
            quant=quant,
            context=context,
            host=effective_host,
            port=port,
            keep_bf16=keep_bf16,
        )

        # install_service() rewrites and reloads the unit, but an already-active
        # service must be explicitly restarted for new host/port arguments to
        # reach the running llama-server process.
        await _apply_inference_networking(
            inference,
            host=effective_host,
            port=port,
            public_access=public_access,
        )

        if public_access:
            click.echo(f"✓ Public inference listener enabled on 0.0.0.0:{port}")
            click.echo("! Router/NAT port forwarding is still required for inbound IPv4 Internet access")
            click.echo("! The endpoint is plain HTTP; use TLS or a VPN before sending API keys over the public Internet")

    _run_cli(run())


@inference_cli.command(name="key")
def inference_key() -> None:
    """Print the API key used by the Atlas inference endpoint."""
    click.echo(Inference(name="Inference").ensure_api_key())


@inference_cli.command(name="status")
def inference_status() -> None:
    """Show the current Atlas inference systemd service status."""
    asyncio.run(Inference(name="Inference").status())


@inference_cli.command(name="validate")
@click.option("--host", default="127.0.0.1", show_default=True, help="Reachable inference address to test.")
@click.option("--port", default=8_080, show_default=True, type=int, help="Inference port to test.")
@click.option("--model", default="Qwen3.8-27B", show_default=True, help="Expected model alias.")
def inference_validate(host: str, port: int, model: str) -> None:
    """Validate the service, HTTP API, advertised model and a real Qwen completion."""
    _run_cli(
        Validation(name="Validation").inference(
            Inference(name="Inference"),
            host=host,
            port=port,
            model=model,
        )
    )


@main.group(name="ohmyzsh")
def ohmyzsh_cli() -> None:
    """Manage the interactive shell and terminal environment on this node."""


@ohmyzsh_cli.command(name="setup")
def ohmyzsh_setup() -> None:
    """Install Oh My Zsh, Powerlevel10k, MesloLGS NF, Terminator and Zsh defaults."""
    asyncio.run(OhMyZsh(name="OhMyZsh").setup())
