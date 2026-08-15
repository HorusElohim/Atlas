from bundle.core import Platform

from atlas.hardware import Gpu, Hardware, _parse_nvidia_smi_gpu


def test_qwen_27b_requires_large_gpu() -> None:
    hardware = Hardware(
        platform=Platform(name="TestPlatform", system="linux", node="atlas-gpu-01", arch="x86_64"),
        gpu=Gpu(name="NVIDIA GeForce RTX 3090", memory_mib=24_576),
    )

    assert hardware.can_run_qwen_27b
    assert not hardware.is_jetson


def test_jetson_memory_is_not_classified_as_27b_inference() -> None:
    hardware = Hardware(
        platform=Platform(name="TestPlatform", system="linux", node="atlas-edge-01", arch="aarch64"),
        memory_mib=8_000,
        gpu=Gpu(name="Orin (nvgpu)", shared_memory=True),
    )

    assert hardware.is_jetson
    assert not hardware.can_run_qwen_27b


def test_jetson_nvidia_smi_unified_memory() -> None:
    gpu = _parse_nvidia_smi_gpu("Orin (nvgpu), [N/A]")

    assert gpu.name == "Orin (nvgpu)"
    assert gpu.memory_mib is None
    assert gpu.shared_memory
