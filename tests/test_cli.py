from click.testing import CliRunner

import atlas.cli as cli


def test_qwen_public_mode_binds_all_interfaces_and_applies_public_networking(monkeypatch) -> None:
    calls: dict[str, object] = {}

    class FakeInference:
        service_name = "atlas-inference"

        def __init__(self, *, name: str) -> None:
            calls["name"] = name

        async def qwen_setup(
            self,
            *,
            quant: str,
            context: int,
            host: str,
            port: int,
            keep_bf16: bool,
        ) -> None:
            calls["setup"] = {
                "quant": quant,
                "context": context,
                "host": host,
                "port": port,
                "keep_bf16": keep_bf16,
            }

    async def fake_networking(
        inference: FakeInference,
        *,
        host: str,
        port: int,
        public_access: bool,
    ) -> None:
        calls["networking"] = {
            "inference": inference,
            "host": host,
            "port": port,
            "public_access": public_access,
        }

    monkeypatch.setattr(cli, "Inference", FakeInference)
    monkeypatch.setattr(cli, "_apply_inference_networking", fake_networking)

    result = CliRunner().invoke(cli.main, ["inference", "qwen", "setup", "--public"])

    assert result.exit_code == 0, result.output
    assert calls["setup"] == {
        "quant": "Q4_K_M",
        "context": 65_536,
        "host": "0.0.0.0",
        "port": 8_080,
        "keep_bf16": False,
    }
    networking = calls["networking"]
    assert isinstance(networking, dict)
    assert networking["host"] == "0.0.0.0"
    assert networking["port"] == 8_080
    assert networking["public_access"] is True
    assert "Public inference listener enabled on 0.0.0.0:8080" in result.output
