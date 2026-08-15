"""Local hardware discovery and capability classification."""

from __future__ import annotations

import platform
import re
from pathlib import Path

from bundle.core import Data, Process


class Gpu(Data):
    """Detected NVIDIA GPU information."""

    name: str
    memory_mib: int


class Hardware(Data):
    """Hardware facts relevant to Atlas deployment decisions."""

    architecture: str
    system: str
    machine: str
    memory_mib: int | None = None
    gpu: Gpu | None = None

    @property
    def can_run_qwen_27b(self) -> bool:
        """Conservative eligibility for a ~17 GiB Q4 27B model on one GPU."""
        return self.gpu is not None and self.gpu.memory_mib >= 22_000

    @classmethod
    async def inspect(cls) -> "Hardware":
        """Inspect the local machine without requiring NVIDIA tooling."""
        return cls(
            architecture=platform.machine(),
            system=platform.system(),
            machine=platform.node(),
            memory_mib=_memory_mib(),
            gpu=await _nvidia_gpu(),
        )


def _memory_mib() -> int | None:
    """Return total system memory from Linux procfs when available."""
    meminfo = Path("/proc/meminfo")
    if not meminfo.exists():
        return None

    match = re.search(r"^MemTotal:\s+(\d+)\s+kB$", meminfo.read_text(), re.MULTILINE)
    return int(match.group(1)) // 1024 if match else None


async def _nvidia_gpu() -> Gpu | None:
    """Return the first discrete NVIDIA GPU reported by nvidia-smi."""
    try:
        result = await Process()(
            "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits"
        )
    except Exception:
        return None

    first = result.stdout.strip().splitlines()
    if not first:
        return None

    name, memory = (part.strip() for part in first[0].rsplit(",", 1))
    return Gpu(name=name, memory_mib=int(memory))
