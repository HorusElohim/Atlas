"""Atlas command-line interface."""

from __future__ import annotations

import asyncio
import json

import rich_click as click

from .hardware import Hardware


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
