"""CUDA llama.cpp inference managed by Atlas."""

from __future__ import annotations

import os
import secrets
import shlex
import shutil
from pathlib import Path

from bundle.core import Entity, Process, ProcessError, ProcessResult, ProcessStream, data, logger

from .hardware import Hardware

log = logger.get_logger(__name__)


class Inference(Entity):
    """Pinned CUDA llama.cpp server for Atlas model inference nodes."""

    llama_repo: str = "https://github.com/ggml-org/llama.cpp.git"
    llama_revision: str = "10bf611e533d81f739128304991c5e133c6aebd8"
    source_model: str = "Qwen/Qwen3.8-27B"
    model_alias: str = "Qwen3.8-27B"

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
    def quantizer(self) -> Path:
        return self.build_dir / "bin" / "llama-quantize"

    @property
    def model_dir(self) -> Path:
        return self.root / "models"

    @property
    def conversion_venv(self) -> Path:
        return self.root / "convert-venv"

    @property
    def conversion_python(self) -> Path:
        return self.conversion_venv / "bin" / "python"

    @property
    def conversion_requirements(self) -> Path:
        return self.source_dir / "requirements" / "requirements-convert_hf_to_gguf.txt"

    @property
    def qwen_bf16(self) -> Path:
        return self.model_dir / f"{self.model_alias}-BF16.gguf"

    def qwen_quantized(self, quant: str) -> Path:
        """Return the local GGUF path for one Qwen quantization."""
        return self.model_dir / f"{self.model_alias}-{quant.upper()}.gguf"

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
        """Install build dependencies for CUDA llama.cpp."""
        await ProcessStream(name="Atlas.Inference.Apt")(
            "sudo apt-get update && "
            "sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y "
            "build-essential ca-certificates cmake curl git libcurl4-openssl-dev ninja-build python3-venv"
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
        """Build llama-server and llama-quantize with CUDA."""
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
            f"cmake --build {shlex.quote(str(self.build_dir))} "
            "--target llama-server llama-quantize --parallel"
        )

        missing = [binary for binary in (self.server, self.quantizer) if not binary.is_file()]
        if missing:
            raise RuntimeError(f"llama.cpp build completed but binaries are missing: {', '.join(map(str, missing))}")

    async def install_conversion_environment(self) -> None:
        """Create the isolated Python environment used by llama.cpp's HF converter."""
        if not self.conversion_python.is_file():
            await ProcessStream(name="Atlas.Qwen.ConvertVenv")(
                f"python3 -m venv {shlex.quote(str(self.conversion_venv))}"
            )

        await ProcessStream(name="Atlas.Qwen.ConvertPip")(
            f"{shlex.quote(str(self.conversion_python))} -m pip install --upgrade pip && "
            f"{shlex.quote(str(self.conversion_python))} -m pip install -r "
            f"{shlex.quote(str(self.conversion_requirements))}"
        )

    def require_conversion_disk(self, *, minimum_gib: int = 80) -> None:
        """Require enough free disk for the temporary BF16 GGUF and final quant."""
        self.model_dir.mkdir(parents=True, exist_ok=True)
        if self.qwen_bf16.is_file():
            return

        free = shutil.disk_usage(self.model_dir).free
        required = minimum_gib * 1024**3
        if free < required:
            free_gib = free / 1024**3
            raise RuntimeError(
                f"Qwen conversion needs about {minimum_gib} GiB of free disk; only {free_gib:.1f} GiB is available "
                f"at {self.model_dir}."
            )

    async def convert_qwen(self) -> Path:
        """Convert the official Qwen3.8-27B safetensors checkpoint to BF16 GGUF remotely."""
        self.model_dir.mkdir(parents=True, exist_ok=True)
        if self.qwen_bf16.is_file():
            log.info("Reusing existing BF16 GGUF: %s", self.qwen_bf16)
            return self.qwen_bf16

        converter = self.source_dir / "convert_hf_to_gguf.py"
        await ProcessStream(name="Atlas.Qwen.Convert")(
            " ".join(
                [
                    shlex.quote(str(self.conversion_python)),
                    shlex.quote(str(converter)),
                    "--remote",
                    "--outtype", "bf16",
                    "--no-mtp",
                    "--outfile", shlex.quote(str(self.qwen_bf16)),
                    shlex.quote(self.source_model),
                ]
            )
        )

        if not self.qwen_bf16.is_file():
            raise RuntimeError(f"Qwen conversion completed but {self.qwen_bf16} was not created.")
        return self.qwen_bf16

    async def quantize_qwen(self, *, quant: str = "Q4_K_M") -> Path:
        """Quantize the BF16 Qwen GGUF for the single-3090 profile."""
        output = self.qwen_quantized(quant)
        if output.is_file():
            log.info("Reusing existing %s GGUF: %s", quant, output)
            return output

        if not self.qwen_bf16.is_file():
            raise RuntimeError("The BF16 Qwen GGUF does not exist; run conversion first.")

        await ProcessStream(name="Atlas.Qwen.Quantize")(
            " ".join(
                [
                    shlex.quote(str(self.quantizer)),
                    shlex.quote(str(self.qwen_bf16)),
                    shlex.quote(str(output)),
                    shlex.quote(quant),
                ]
            )
        )

        if not output.is_file():
            raise RuntimeError(f"Qwen quantization completed but {output} was not created.")
        return output

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
        hf_repo: str | None = None,
        model_path: Path | None = None,
        quant: str = "Q4_K_M",
        context: int = 65_536,
        host: str = "127.0.0.1",
        port: int = 8_080,
    ) -> str:
        """Render the systemd unit for one local or Hugging Face GGUF-backed model server."""
        if (hf_repo is None) == (model_path is None):
            raise ValueError("Specify exactly one of hf_repo or model_path.")

        user = os.environ.get("USER")
        if not user:
            raise RuntimeError("USER is not set; cannot create the inference service safely.")

        args = [str(self.server)]
        if model_path is not None:
            args.extend(["--model", str(model_path)])
        else:
            args.extend(["--hf-repo", f"{hf_repo}:{quant}"])

        args.extend(
            [
                "--alias", self.model_alias,
                "--host", host,
                "--port", str(port),
                "--ctx-size", str(context),
                "--parallel", "1",
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
        )
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
        hf_repo: str | None = None,
        model_path: Path | None = None,
        quant: str = "Q4_K_M",
        context: int = 65_536,
        host: str = "127.0.0.1",
        port: int = 8_080,
    ) -> None:
        """Install and start the authenticated systemd inference service."""
        self.ensure_api_key()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        unit = self.service_content(
            hf_repo=hf_repo,
            model_path=model_path,
            quant=quant,
            context=context,
            host=host,
            port=port,
        )
        temporary = self.config_dir / f"{self.service_name}.service"
        temporary.write_text(unit, encoding="utf-8")

        await ProcessStream(name="Atlas.Inference.Systemd.Install")(
            f"sudo install -m 0644 {shlex.quote(str(temporary))} {shlex.quote(str(self.unit_file))}"
        )
        await ProcessStream(name="Atlas.Inference.Systemd.Reload")("sudo systemctl daemon-reload")
        await ProcessStream(name="Atlas.Inference.Systemd.Enable")(
            f"sudo systemctl enable --now {shlex.quote(self.service_name)}"
        )
        await self.wait_ready(host=host, port=port)

    async def wait_ready(self, *, host: str, port: int) -> ProcessResult:
        """Wait until llama-server has loaded the model and reports healthy."""
        health_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
        url = f"http://{health_host}:{port}/health"
        command = (
            "for attempt in $(seq 1 360); do "
            f"if curl -fsS {shlex.quote(url)} >/dev/null 2>&1; then exit 0; fi; "
            "sleep 5; "
            "done; "
            f"echo 'Timed out waiting for {shlex.quote(url)}' >&2; exit 1"
        )
        return await ProcessStream(name="Atlas.Inference.Health")(command)

    async def status(self) -> ProcessResult | None:
        """Show the inference state without treating an unconfigured model service as an error."""
        if not self.unit_file.is_file():
            if self.server.is_file():
                log.info("llama.cpp CUDA engine is ready at %s", self.server)
            else:
                log.info("llama.cpp CUDA engine is not built yet; run `atlas inference setup`.")

            qwen = self.qwen_quantized("Q4_K_M")
            if qwen.is_file():
                log.info("Qwen model is ready at %s", qwen)
                log.info("Run `atlas inference qwen setup` to install its service.")
            else:
                log.info("No model service is configured yet.")
                log.info("Run `atlas inference qwen setup` to prepare Qwen3.8-27B automatically.")
            return None

        return await ProcessStream(name="Atlas.Inference.Status")(
            f"systemctl status {shlex.quote(self.service_name)} --no-pager"
        )

    async def qwen_setup(
        self,
        *,
        quant: str = "Q4_K_M",
        context: int = 65_536,
        host: str = "127.0.0.1",
        port: int = 8_080,
        keep_bf16: bool = False,
    ) -> Path:
        """Prepare, convert, quantize and serve Qwen3.8-27B end-to-end."""
        hardware = await self.validate_hardware()
        log.info("Preparing %s on %s (%s MiB VRAM)", self.model_alias, hardware.gpu.name, hardware.gpu.memory_mib)

        await self.install_packages()
        await self.checkout()
        await self.build()

        quantized = self.qwen_quantized(quant)
        if not quantized.is_file():
            self.require_conversion_disk()
            await self.install_conversion_environment()
            await self.convert_qwen()
            quantized = await self.quantize_qwen(quant=quant)

        if not keep_bf16 and self.qwen_bf16.is_file():
            self.qwen_bf16.unlink()
            log.info("Removed intermediate BF16 GGUF: %s", self.qwen_bf16)

        await self.install_service(
            model_path=quantized,
            quant=quant,
            context=context,
            host=host,
            port=port,
        )
        log.info("%s inference is ready at %s:%s/v1", self.model_alias, host, port)
        return quantized

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
            log.info("Run `atlas inference qwen setup` to convert, quantize and deploy it automatically.")
            return

        await self.install_service(hf_repo=hf_repo, quant=quant, context=context, host=host, port=port)
        log.info("Inference service ready: %s:%s (%s as %s)", host, port, f"{hf_repo}:{quant}", self.model_alias)
