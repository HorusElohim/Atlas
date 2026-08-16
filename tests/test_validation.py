from pathlib import Path

import yaml

from atlas.hermes import Hermes
from atlas.validation import Validation


def test_model_ids_extract_openai_catalog() -> None:
    validation = Validation(name="TestValidation")

    assert validation._model_ids(
        {
            "object": "list",
            "data": [
                {"id": "Qwen3.8-27B", "object": "model"},
                {"id": "other", "object": "model"},
                {"not_id": "ignored"},
            ],
        }
    ) == ["Qwen3.8-27B", "other"]


def test_configured_hermes_target_reads_named_atlas_provider(tmp_path: Path) -> None:
    home = tmp_path / ".hermes"
    home.mkdir()

    config = {
        "model": {
            "default": "Qwen3.8-27B",
            "provider": "custom:atlas",
        },
        "providers": {
            "atlas": {
                "api": "http://127.0.0.1:8080/v1",
                "key_env": "ATLAS_INFERENCE_API_KEY",
                "transport": "chat_completions",
                "default_model": "Qwen3.8-27B",
            }
        },
    }
    (home / "config.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    (home / ".env").write_text("ATLAS_INFERENCE_API_KEY=secret\n", encoding="utf-8")

    hermes = Hermes(name="TestHermes", home=home, system_launcher=tmp_path / "hermes")
    target = Validation(name="TestValidation")._configured_hermes_target(hermes)

    assert target == ("http://127.0.0.1:8080/v1", "secret", "Qwen3.8-27B")


def test_completion_extracts_content_and_reasoning(monkeypatch) -> None:
    validation = Validation(name="TestValidation")

    monkeypatch.setattr(
        Validation,
        "_request_json",
        staticmethod(
            lambda *args, **kwargs: {
                "choices": [
                    {
                        "message": {
                            "content": "ATLAS_QWEN_OK",
                            "reasoning_content": "checked",
                        }
                    }
                ]
            }
        ),
    )

    reply = validation._completion(
        "http://127.0.0.1:8080/v1",
        "secret",
        "Qwen3.8-27B",
        "test",
    )

    assert reply == "ATLAS_QWEN_OK\nchecked"
