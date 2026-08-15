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
@click.option("--quick", is_flag=True, help="Only prompt for missing or unset Hermes settings.")
def hermes_setup(quick: bool) -> None:
    """Install Hermes, run its setup wizard, enforce native execution, and verify it."""
    asyncio.run(Hermes(name="Hermes").setup(quick=quick))


@hermes_cli.command(name="expose")
def hermes_expose() -> None:
    """Expose the Hermes launcher at /usr/local/bin/hermes."""
    asyncio.run(Hermes(name="Hermes").expose())


@hermes_cli.command(name="doctor")
@click.option("--fix", is_flag=True, help="Apply Hermes automatic configuration and state fixes.")
@click.option("--strict", is_flag=True, help="Fail when Hermes reports an incomplete configuration.")
def hermes_doctor(fix: bool, strict: bool) -> None:
    """Run Hermes diagnostics."""
    asyncio.run(Hermes(name="Hermes").doctor(strict=strict, fix=fix))


@main.group(name="ohmyzsh")
def ohmyzsh_cli() -> None:
    """Manage the interactive shell and terminal environment on this node."""


@ohmyzsh_cli.command(name="setup")
def ohmyzsh_setup() -> None:
    """Install Oh My Zsh, Powerlevel10k, MesloLGS NF, Terminator and Zsh defaults."""
    asyncio.run(OhMyZsh(name="OhMyZsh").setup())
