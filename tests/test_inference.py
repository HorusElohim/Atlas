from pathlib import Path

from atlas.inference import Inference


def test_service_content_uses_authenticated_qwen_profile(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("USER", "atlas")
    monkeypatch.setenv("HOME", str(tmp_path))

    inference = Inference(
        name="TestInference",
        root=tmp_path / "share" / "inference",
        config_dir=tmp_path / "config" / "inference",
        cache_dir=tmp_path / "cache" / "llama.cpp",
    )

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


def test_api_key_is_created_once(tmp_path: Path) -> None:
    inference = Inference(
        name="TestInference",
        root=tmp_path / "share" / "inference",
        config_dir=tmp_path / "config" / "inference",
        cache_dir=tmp_path / "cache" / "llama.cpp",
    )

    first = inference.ensure_api_key()
    second = inference.ensure_api_key()

    assert first == second
    assert len(first) >= 32
    assert inference.api_key_file.stat().st_mode & 0o777 == 0o600
