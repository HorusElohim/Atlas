"""Local hardware discovery and capability classification."""

from __future__ import annotations

import re
from pathlib import Path

from bundle.core import Data, Platform, Process, platform_info


class Gpu(Data):
    """Detected NVIDIA GPU information."""

    name: str
    memory_mib: int | None = None
    shared_memory: bool = False


class Hardware(Data):
    """Hardware facts relevant to Atlas deployment decisions."""

    platform: Platform
    device_model: str | None = None
    memory_mib: int | None = None
    gpu: Gpu | None = None

    @property
    def can_run_qwen_27b(self) -> bool:
        """Conservative eligibility for a ~17 GiB Q4 27B model on one GPU."""
        return self.gpu is not None and self.gpu.memory_mib is not None and self.gpu.memory_mib >= 22_000

    @classmethod
    async def inspect(cls) -> "Hardware":
        """Inspect the local machine using Bundle as the platform source of truth."""
        return cls(
            platform=platform_info,
            device_model=_device_model(),
            memory_mib=_memory_mib(),
            gpu=await _nvidia_gpu(),
        )


def _device_model() -> str | None:
    """Return the firmware-provided device model when Linux exposes one."""
    model = Path("/proc/device-tree/model")
    if not model.exists():
        return None

    value = model.read_bytes().rstrip(b"\x00").decode("utf-8", errors="replace").strip()
    return value or None


def _memory_mib() -> int | None:
    """Return total system memory from Linux procfs when available."""
    meminfo = Path("/proc/meminfo")
    if not meminfo.exists():
        return None

    match = re.search(r"^MemTotal:\s+(\d+)\s+kB$", meminfo.read_text(), re.MULTILINE)
    return int(match.group(1)) // 1024 if match else None


def _parse_nvidia_smi_gpu(line: str) -> Gpu:
    """Parse one nvidia-smi CSV row, including Jetson's unified-memory output."""
    name, memory = (part.strip() for part in line.rsplit(",", 1))
    memory_mib = int(memory) if memory.isdigit() else None
    return Gpu(name=name, memory_mib=memory_mib, shared_memory=memory_mib is None)


async def _nvidia_gpu() -> Gpu | None:
    """Return the first NVIDIA GPU reported by nvidia-smi."""
    try:
        result = await Process(name="Atlas.NvidiaGpu")(
            "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits"
        )
    except Exception:
        return None

    lines = result.stdout.strip().splitlines()
    return _parse_nvidia_smi_gpu(lines[0]) if lines else None
