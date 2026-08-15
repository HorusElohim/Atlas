"""Atlas command-line interface."""

from __future__ import annotations

import asyncio
import json

import rich_click as click

from .hardware import Hardware
from .hermes import Hermes
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
def hermes_setup() -> None:
    """Install Hermes natively, select the local terminal backend, and run diagnostics."""
    asyncio.run(Hermes(name="Hermes").setup())


@hermes_cli.command(name="doctor")
@click.option("--strict", is_flag=True, help="Fail when Hermes reports an incomplete configuration.")
def hermes_doctor(strict: bool) -> None:
    """Run Hermes diagnostics."""
    asyncio.run(Hermes(name="Hermes").doctor(strict=strict))


@main.group(name="ohmyzsh")
def ohmyzsh_cli() -> None:
    """Manage the interactive Zsh environment on this node."""


@ohmyzsh_cli.command(name="setup")
def ohmyzsh_setup() -> None:
    """Install Oh My Zsh, Powerlevel10k, MesloLGS NF and make Zsh the login shell."""
    asyncio.run(OhMyZsh(name="OhMyZsh").setup())
