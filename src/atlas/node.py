"""Atlas node models."""

from __future__ import annotations

from enum import StrEnum

from bundle.core import Data

from .hardware import Hardware


class NodeRole(StrEnum):
    """A capability role assigned to an Atlas node."""

    AGENT = "agent"
    INFERENCE = "inference"
    EDGE = "edge"


class Node(Data):
    """A machine participating in an Atlas fleet."""

    name: str
    host: str = "localhost"
    roles: set[NodeRole] = {NodeRole.AGENT}
    hardware: Hardware | None = None

    @property
    def can_infer(self) -> bool:
        """Whether the node is suitable for large local-model inference."""
        return self.hardware is not None and self.hardware.can_run_qwen_27b
