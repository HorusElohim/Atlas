from atlas.hardware import Gpu, Hardware


def test_qwen_27b_requires_large_gpu() -> None:
    hardware = Hardware(
        architecture="x86_64",
        system="Linux",
        machine="atlas-gpu-01",
        gpu=Gpu(name="NVIDIA GeForce RTX 3090", memory_mib=24_576),
    )

    assert hardware.can_run_qwen_27b


def test_jetson_memory_is_not_classified_as_27b_inference() -> None:
    hardware = Hardware(
        architecture="aarch64",
        system="Linux",
        machine="atlas-edge-01",
        memory_mib=8_000,
    )

    assert not hardware.can_run_qwen_27b
