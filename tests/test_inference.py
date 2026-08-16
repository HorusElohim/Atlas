from pathlib import Path

from atlas.inference import Inference


def make_inference(tmp_path: Path) -> Inference:
    return Inference(
        name="TestInference",
        root=tmp_path / "share" / "inference",
        config_dir=tmp_path / "config" / "inference",
        cache_dir=tmp_path / "cache" / "llama.cpp",
    )


def test_service_content_uses_authenticated_qwen_profile(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("USER", "atlas")
    monkeypatch.setenv("HOME", str(tmp_path))

    inference = make_inference(tmp_path)
    content = inference.service_content(
        hf_repo="example/Qwen3.8-27B-GGUF",
        quant="Q4_K_M",
        context=65_536,
        host="127.0.0.1",
        port=8_080,
    )

    assert "User=atlas" in content
    assert "--hf-repo example/Qwen3.8-27B-GGUF:Q4_K_M" in content
    assert "--alias Qwen3.8-27B" in content
    assert "--ctx-size 65536" in content
    assert "--parallel 1" in content
    assert "--n-gpu-layers all" in content
    assert "--split-mode none" in content
    assert "--flash-attn on" in content
    assert "--cache-type-k q4_0" in content
    assert "--cache-type-v q4_0" in content
    assert "--api-key-file" in content
    assert "--host 127.0.0.1" in content
    assert "--no-webui" in content


def test_service_content_can_load_local_qwen_gguf(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("USER", "atlas")
    monkeypatch.setenv("HOME", str(tmp_path))

    inference = make_inference(tmp_path)
    model = inference.qwen_quantized("Q4_K_M")
    content = inference.service_content(model_path=model, host="0.0.0.0")

    assert f"--model {model}" in content
    assert "--hf-repo" not in content
    assert "--alias Qwen3.8-27B" in content
    assert "--host 0.0.0.0" in content


def test_qwen_model_paths_are_stable(tmp_path: Path) -> None:
    inference = make_inference(tmp_path)

    assert inference.qwen_bf16.name == "Qwen3.8-27B-BF16.gguf"
    assert inference.qwen_quantized("q4_k_m").name == "Qwen3.8-27B-Q4_K_M.gguf"
    assert inference.conversion_python == inference.root / "convert-venv" / "bin" / "python"


def test_api_key_is_created_once(tmp_path: Path) -> None:
    inference = make_inference(tmp_path)

    first = inference.ensure_api_key()
    second = inference.ensure_api_key()

    assert first == second
    assert len(first) >= 32
    assert inference.api_key_file.stat().st_mode & 0o777 == 0o600
