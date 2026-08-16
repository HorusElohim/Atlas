"""Atlas command-line interface."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import rich_click as click

from .hardware import Hardware
from .hermes import Hermes
from .inference import Inference
from .ohmyzsh import OhMyZsh


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

    asyncio.run(
        Hermes(name="Hermes").connect(
            base_url,
            api_key,
            model=model,
            context=context,
        )
    )


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


@inference_cli.command(name="key")
def inference_key() -> None:
    """Print the API key used by the Atlas inference endpoint."""
    click.echo(Inference(name="Inference").ensure_api_key())


@inference_cli.command(name="status")
def inference_status() -> None:
    """Show the current Atlas inference systemd service status."""
    asyncio.run(Inference(name="Inference").status())


@main.group(name="ohmyzsh")
def ohmyzsh_cli() -> None:
    """Manage the interactive shell and terminal environment on this node."""


@ohmyzsh_cli.command(name="setup")
def ohmyzsh_setup() -> None:
    """Install Oh My Zsh, Powerlevel10k, MesloLGS NF, Terminator and Zsh defaults."""
    asyncio.run(OhMyZsh(name="OhMyZsh").setup())
