from bundle.core import Platform

from atlas.hardware import Gpu, Hardware


def test_qwen_27b_requires_large_gpu() -> None:
    hardware = Hardware(
        platform=Platform(name="TestPlatform", system="linux", node="atlas-gpu-01", arch="x86_64"),
        gpu=Gpu(name="NVIDIA GeForce RTX 3090", memory_mib=24_576),
    )

    assert hardware.can_run_qwen_27b


def test_jetson_memory_is_not_classified_as_27b_inference() -> None:
    hardware = Hardware(
        platform=Platform(name="TestPlatform", system="linux", node="atlas-edge-01", arch="aarch64"),
        memory_mib=8_000,
    )

    assert not hardware.can_run_qwen_27b
