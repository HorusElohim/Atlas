"""CUDA llama.cpp inference managed by Atlas."""

from __future__ import annotations

import os
import secrets
import shlex
from pathlib import Path

from bundle.core import Entity, Process, ProcessError, ProcessResult, ProcessStream, data, logger

from .hardware import Hardware

log = logger.get_logger(__name__)


class Inference(Entity):
    """Pinned CUDA llama.cpp server for Atlas model inference nodes."""

    llama_repo: str = "https://github.com/ggml-org/llama.cpp.git"
    llama_revision: str = "10bf611e533d81f739128304991c5e133c6aebd8"
    source_model: str = "Qwen/Qwen3.8-27B"

    root: Path = data.Field(default_factory=lambda: Path.home() / ".local" / "share" / "atlas" / "inference")
    config_dir: Path = data.Field(default_factory=lambda: Path.home() / ".config" / "atlas" / "inference")
    cache_dir: Path = data.Field(default_factory=lambda: Path.home() / ".cache" / "llama.cpp")
    service_name: str = "atlas-inference"

    @property
    def source_dir(self) -> Path:
        return self.root / "llama.cpp"

    @property
    def build_dir(self) -> Path:
        return self.source_dir / "build-atlas"

    @property
    def server(self) -> Path:
        return self.build_dir / "bin" / "llama-server"

    @property
    def api_key_file(self) -> Path:
        return self.config_dir / "api-key"

    @property
    def unit_file(self) -> Path:
        return Path("/etc/systemd/system") / f"{self.service_name}.service"

    async def validate_hardware(self) -> Hardware:
        """Require a discrete NVIDIA GPU with enough VRAM for the 27B Q4 profile."""
        hardware = await Hardware.inspect()
        gpu = hardware.gpu
        if gpu is None:
            raise RuntimeError("No NVIDIA GPU was detected; Atlas inference requires a CUDA-capable GPU.")
        if gpu.memory_mib is None:
            raise RuntimeError(
                f"{gpu.name} uses shared/unreported GPU memory; deploy the 27B inference profile on a discrete GPU node."
            )
        if gpu.memory_mib < 22_000:
            raise RuntimeError(
                f"{gpu.name} reports {gpu.memory_mib} MiB VRAM; Atlas requires at least 22000 MiB for the 27B profile."
            )

        try:
            await Process(name="Atlas.Inference.Nvcc")("nvcc --version")
        except ProcessError as error:
            raise RuntimeError(
                "NVIDIA CUDA toolkit/nvcc was not found. Install the CUDA toolkit appropriate for this host first."
            ) from error

        return hardware

    async def install_packages(self) -> None:
        """Install build and Hugging Face download dependencies for llama.cpp."""
        await ProcessStream(name="Atlas.Inference.Apt")(
            "sudo apt-get update && "
            "sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y "
            "build-essential ca-certificates cmake git libcurl4-openssl-dev ninja-build"
        )

    async def checkout(self) -> None:
        """Checkout the exact llama.cpp revision tested by Atlas."""
        self.root.mkdir(parents=True, exist_ok=True)

        if not (self.source_dir / ".git").is_dir():
            if self.source_dir.exists():
                raise RuntimeError(f"{self.source_dir} exists but is not a git checkout.")
            await ProcessStream(name="Atlas.LlamaCpp.Clone")(
                f"git clone {shlex.quote(self.llama_repo)} {shlex.quote(str(self.source_dir))}"
            )

        await ProcessStream(name="Atlas.LlamaCpp.Fetch")(
            f"git -C {shlex.quote(str(self.source_dir))} fetch --force origin {shlex.quote(self.llama_revision)}"
        )
        await ProcessStream(name="Atlas.LlamaCpp.Checkout")(
            f"git -C {shlex.quote(str(self.source_dir))} checkout --detach {shlex.quote(self.llama_revision)}"
        )

    async def build(self) -> None:
        """Build llama-server with CUDA and libcurl-backed Hugging Face support."""
        configure = " ".join(
            [
                "cmake",
                "-S", shlex.quote(str(self.source_dir)),
                "-B", shlex.quote(str(self.build_dir)),
                "-G", "Ninja",
                "-DCMAKE_BUILD_TYPE=Release",
                "-DGGML_CUDA=ON",
                "-DLLAMA_BUILD_TESTS=OFF",
                "-DBUILD_SHARED_LIBS=OFF",
            ]
        )
        await ProcessStream(name="Atlas.LlamaCpp.Configure")(configure)
        await ProcessStream(name="Atlas.LlamaCpp.Build")(
            f"cmake --build {shlex.quote(str(self.build_dir))} --target llama-server --parallel"
        )

        if not self.server.is_file():
            raise RuntimeError(f"llama-server build completed but {self.server} was not created.")

    def ensure_api_key(self) -> str:
        """Create and persist a private API key for the inference endpoint."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        if self.api_key_file.is_file():
            return self.api_key_file.read_text(encoding="utf-8").strip()

        key = secrets.token_urlsafe(32)
        self.api_key_file.write_text(key + "\n", encoding="utf-8")
        self.api_key_file.chmod(0o600)
        return key

    def service_content(
        self,
        *,
        hf_repo: str,
        quant: str = "Q4_K_M",
        context: int = 65_536,
        host: str = "127.0.0.1",
        port: int = 8_080,
    ) -> str:
        """Render the systemd unit for one pinned GGUF-backed model server."""
        user = os.environ.get("USER")
        if not user:
            raise RuntimeError("USER is not set; cannot create the inference service safely.")

        model = f"{hf_repo}:{quant}"
        args = [
            str(self.server),
            "--hf-repo", model,
            "--host", host,
            "--port", str(port),
            "--ctx-size", str(context),
            "--n-gpu-layers", "all",
            "--split-mode", "none",
            "--flash-attn", "on",
            "--cache-type-k", "q4_0",
            "--cache-type-v", "q4_0",
            "--api-key-file", str(self.api_key_file),
            "--jinja",
            "--reasoning", "auto",
            "--metrics",
            "--no-webui",
        ]
        exec_start = " ".join(shlex.quote(arg) for arg in args)

        return (
            "[Unit]\n"
            "Description=Atlas llama.cpp inference server\n"
            "After=network-online.target\n"
            "Wants=network-online.target\n\n"
            "[Service]\n"
            "Type=simple\n"
            f"User={user}\n"
            f"Environment=HOME={Path.home()}\n"
            f"Environment=LLAMA_CACHE={self.cache_dir}\n"
            f"ExecStart={exec_start}\n"
            "Restart=on-failure\n"
            "RestartSec=5\n"
            "TimeoutStartSec=0\n"
            "LimitNOFILE=1048576\n\n"
            "[Install]\n"
            "WantedBy=multi-user.target\n"
        )

    async def install_service(
        self,
        *,
        hf_repo: str,
        quant: str = "Q4_K_M",
        context: int = 65_536,
        host: str = "127.0.0.1",
        port: int = 8_080,
    ) -> None:
        """Install and start the authenticated systemd inference service."""
        self.ensure_api_key()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        unit = self.service_content(hf_repo=hf_repo, quant=quant, context=context, host=host, port=port)
        temporary = self.config_dir / f"{self.service_name}.service"
        temporary.write_text(unit, encoding="utf-8")

        await ProcessStream(name="Atlas.Inference.Systemd.Install")(
            f"sudo install -m 0644 {shlex.quote(str(temporary))} {shlex.quote(str(self.unit_file))}"
        )
        await ProcessStream(name="Atlas.Inference.Systemd.Reload")("sudo systemctl daemon-reload")
        await ProcessStream(name="Atlas.Inference.Systemd.Enable")(
            f"sudo systemctl enable --now {shlex.quote(self.service_name)}"
        )

    async def status(self) -> ProcessResult:
        """Show systemd status for the inference service."""
        return await ProcessStream(name="Atlas.Inference.Status")(
            f"systemctl status {shlex.quote(self.service_name)} --no-pager"
        )

    async def setup(
        self,
        *,
        hf_repo: str | None = None,
        quant: str = "Q4_K_M",
        context: int = 65_536,
        host: str = "127.0.0.1",
        port: int = 8_080,
    ) -> None:
        """Prepare the engine and optionally deploy a verified GGUF repository."""
        hardware = await self.validate_hardware()
        log.info("Preparing inference on %s (%s MiB VRAM)", hardware.gpu.name, hardware.gpu.memory_mib)
        await self.install_packages()
        await self.checkout()
        await self.build()

        if hf_repo is None:
            log.info("llama.cpp CUDA engine is ready at %s", self.server)
            log.info("Qwen source model: %s", self.source_model)
            log.info("No GGUF repository selected yet; engine setup is complete without starting a model service.")
            return

        await self.install_service(hf_repo=hf_repo, quant=quant, context=context, host=host, port=port)
        log.info("Inference service installed: %s:%s (%s)", host, port, f"{hf_repo}:{quant}")
