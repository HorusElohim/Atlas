from pathlib import Path

import yaml

from atlas.hermes import Hermes


def test_configure_atlas_provider_preserves_unrelated_settings(tmp_path: Path) -> None:
    home = tmp_path / ".hermes"
    home.mkdir()
    config_file = home / "config.yaml"
    config_file.write_text(
        "terminal:\n"
        "  backend: local\n"
        "model:\n"
        "  default: old-model\n"
        "  provider: custom\n"
        "  base_url: http://old.invalid/v1\n"
        "  context_length: 64000\n"
        "providers:\n"
        "  other:\n"
        "    api: https://example.invalid/v1\n",
        encoding="utf-8",
    )

    env_file = home / ".env"
    env_file.write_text("OTHER_SECRET=keep-me\nATLAS_INFERENCE_API_KEY=old\n", encoding="utf-8")

    hermes = Hermes(name="TestHermes", home=home, system_launcher=tmp_path / "hermes")
    hermes._configure_atlas_provider(
        "http://atlas-gpu-01:8080/v1",
        "new-secret",
        model="Qwen3.8-27B",
        context=65_536,
    )

    config = yaml.safe_load(config_file.read_text(encoding="utf-8"))

    assert config["terminal"]["backend"] == "local"
    assert config["providers"]["other"]["api"] == "https://example.invalid/v1"
    assert config["providers"]["atlas"] == {
        "api": "http://atlas-gpu-01:8080/v1",
        "key_env": "ATLAS_INFERENCE_API_KEY",
        "transport": "chat_completions",
        "default_model": "Qwen3.8-27B",
        "models": {"Qwen3.8-27B": {"context_length": 65_536}},
    }
    assert config["model"]["default"] == "Qwen3.8-27B"
    assert config["model"]["provider"] == "custom:atlas"
    assert "base_url" not in config["model"]
    assert "context_length" not in config["model"]

    env = env_file.read_text(encoding="utf-8")
    assert "OTHER_SECRET=keep-me" in env
    assert env.count("ATLAS_INFERENCE_API_KEY=new-secret") == 1
    assert "ATLAS_INFERENCE_API_KEY=old" not in env
    assert env_file.stat().st_mode & 0o777 == 0o600
