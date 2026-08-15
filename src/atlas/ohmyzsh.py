"""Oh My Zsh, Powerlevel10k and terminal setup managed by Atlas."""

from __future__ import annotations

import os
import re
import shlex
import shutil
from pathlib import Path

from bundle.core import Entity, Process, ProcessError, ProcessStream, data, logger

log = logger.get_logger(__name__)


class OhMyZsh(Entity):
    """Idempotent Oh My Zsh, Powerlevel10k, MesloLGS NF and Terminator setup."""

    home: Path = data.Field(default_factory=Path.home)
    oh_my_zsh_url: str = "https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh"
    powerlevel10k_url: str = "https://github.com/romkatv/powerlevel10k.git"
    font_base_url: str = "https://raw.githubusercontent.com/romkatv/powerlevel10k-media/master"

    @property
    def oh_my_zsh(self) -> Path:
        return self.home / ".oh-my-zsh"

    @property
    def zshrc(self) -> Path:
        return self.home / ".zshrc"

    @property
    def powerlevel10k(self) -> Path:
        custom = Path(os.environ.get("ZSH_CUSTOM", self.oh_my_zsh / "custom"))
        return custom / "themes" / "powerlevel10k"

    @property
    def font_dir(self) -> Path:
        return self.home / ".local" / "share" / "fonts" / "MesloLGS-NF"

    @property
    def terminator_config(self) -> Path:
        return self.home / ".config" / "terminator" / "config"

    async def install_packages(self) -> None:
        """Install the Linux packages required by the interactive environment."""
        await ProcessStream(name="Atlas.OhMyZsh.Apt")(
            "sudo apt-get update && "
            "sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y "
            "zsh fontconfig curl git terminator"
        )

    async def install_oh_my_zsh(self) -> None:
        """Install Oh My Zsh without replacing an existing .zshrc or starting a shell."""
        if self.oh_my_zsh.is_dir():
            log.info("Oh My Zsh is already installed at %s", self.oh_my_zsh)
            return

        await ProcessStream(name="Atlas.OhMyZsh.Install")(
            "KEEP_ZSHRC=yes RUNZSH=no CHSH=no "
            f"sh -c \"$(curl -fsSL {shlex.quote(self.oh_my_zsh_url)})\" \"\" "
            "--unattended --keep-zshrc"
        )

        if not self.oh_my_zsh.is_dir():
            raise RuntimeError("Oh My Zsh installer completed but ~/.oh-my-zsh was not created.")

    async def install_powerlevel10k(self) -> None:
        """Install or fast-forward the Powerlevel10k Oh My Zsh theme."""
        self.powerlevel10k.parent.mkdir(parents=True, exist_ok=True)

        if (self.powerlevel10k / ".git").is_dir():
            await ProcessStream(name="Atlas.Powerlevel10k.Update")(
                f"git -C {shlex.quote(str(self.powerlevel10k))} pull --ff-only"
            )
            return

        if self.powerlevel10k.exists():
            raise RuntimeError(f"{self.powerlevel10k} exists but is not a git checkout.")

        await ProcessStream(name="Atlas.Powerlevel10k.Install")(
            f"git clone --depth=1 {shlex.quote(self.powerlevel10k_url)} "
            f"{shlex.quote(str(self.powerlevel10k))}"
        )

    async def install_fonts(self) -> None:
        """Install Powerlevel10k's recommended MesloLGS NF fonts for this user."""
        self.font_dir.mkdir(parents=True, exist_ok=True)

        fonts = {
            "MesloLGS NF Regular.ttf": "MesloLGS%20NF%20Regular.ttf",
            "MesloLGS NF Bold.ttf": "MesloLGS%20NF%20Bold.ttf",
            "MesloLGS NF Italic.ttf": "MesloLGS%20NF%20Italic.ttf",
            "MesloLGS NF Bold Italic.ttf": "MesloLGS%20NF%20Bold%20Italic.ttf",
        }

        for filename, remote_name in fonts.items():
            destination = self.font_dir / filename
            if destination.is_file():
                continue

            await ProcessStream(name=f"Atlas.Font.{filename}")(
                f"curl -fL --retry 3 -o {shlex.quote(str(destination))} "
                f"{shlex.quote(f'{self.font_base_url}/{remote_name}')}"
            )

        await ProcessStream(name="Atlas.Font.Cache")("fc-cache -f")

    def configure_zshrc(self) -> None:
        """Wire Oh My Zsh and Powerlevel10k while preserving user configuration."""
        content = self.zshrc.read_text(encoding="utf-8") if self.zshrc.exists() else ""
        theme = 'ZSH_THEME="powerlevel10k/powerlevel10k"'
        p10k_source = '[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh'
        local_bin_path = 'export PATH="$HOME/.local/bin:$PATH"'

        lines = [
            line
            for line in content.splitlines()
            if not re.match(r"^\s*ZSH_THEME=", line) and line.strip() != p10k_source
        ]

        has_local_bin = any(
            "PATH=" in line and ("$HOME/.local/bin" in line or "${HOME}/.local/bin" in line or "~/.local/bin" in line)
            for line in lines
        )
        if not has_local_bin:
            lines.insert(0, local_bin_path)

        source_index = next(
            (
                index
                for index, line in enumerate(lines)
                if "oh-my-zsh.sh" in line and not line.lstrip().startswith("#")
            ),
            None,
        )

        has_zsh_before_source = any(
            re.match(r"^\s*(?:export\s+)?ZSH=", line)
            for line in lines[:source_index] if source_index is not None
        )
        has_zsh = any(re.match(r"^\s*(?:export\s+)?ZSH=", line) for line in lines)

        if source_index is not None:
            if not has_zsh_before_source:
                lines.insert(source_index, 'export ZSH="$HOME/.oh-my-zsh"')
                source_index += 1
            lines.insert(source_index, theme)
        else:
            if lines and lines[-1].strip():
                lines.append("")
            if not has_zsh:
                lines.append('export ZSH="$HOME/.oh-my-zsh"')
            lines.append(theme)
            if not any(re.match(r"^\s*plugins=", line) for line in lines):
                lines.append("plugins=(git)")
            lines.append("source $ZSH/oh-my-zsh.sh")

        if lines and lines[-1].strip():
            lines.append("")
        lines.append(p10k_source)

        self.zshrc.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def configure_terminator(self) -> None:
        """Configure Terminator's default profile with the Powerlevel10k font."""
        self.terminator_config.parent.mkdir(parents=True, exist_ok=True)
        content = self.terminator_config.read_text(encoding="utf-8") if self.terminator_config.exists() else ""
        lines = content.splitlines()

        if not lines:
            lines = [
                "[global_config]",
                "[keybindings]",
                "[profiles]",
                "  [[default]]",
                "    use_system_font = False",
                "    font = MesloLGS NF Regular 11",
                "[layouts]",
                "  [[default]]",
                "    [[[window0]]]",
                '      type = Window',
                '      parent = ""',
                "    [[[child1]]]",
                "      type = Terminal",
                "      parent = window0",
                "[plugins]",
            ]
        else:
            lines = self._patch_terminator_default_profile(lines)

        self.terminator_config.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    @staticmethod
    def _patch_terminator_default_profile(lines: list[str]) -> list[str]:
        """Patch only the default Terminator profile while preserving the rest of the config."""
        output: list[str] = []
        in_profiles = False
        in_default = False
        profiles_seen = False
        default_seen = False
        font_seen = False
        system_font_seen = False

        def finish_default() -> None:
            nonlocal font_seen, system_font_seen
            if not in_default:
                return
            if not system_font_seen:
                output.append("    use_system_font = False")
            if not font_seen:
                output.append("    font = MesloLGS NF Regular 11")
            font_seen = False
            system_font_seen = False

        for line in lines:
            stripped = line.strip()
            top_level = bool(re.fullmatch(r"\[[^\[\]]+\]", stripped))
            subsection = bool(re.fullmatch(r"\[\[[^\[\]]+\]\]", stripped))

            if top_level:
                if in_default:
                    finish_default()
                    in_default = False
                if in_profiles and not default_seen:
                    output.extend([
                        "  [[default]]",
                        "    use_system_font = False",
                        "    font = MesloLGS NF Regular 11",
                    ])
                    default_seen = True
                in_profiles = stripped == "[profiles]"
                profiles_seen = profiles_seen or in_profiles
                output.append(line)
                continue

            if in_profiles and subsection:
                if in_default:
                    finish_default()
                in_default = stripped == "[[default]]"
                if in_default:
                    default_seen = True
                    font_seen = False
                    system_font_seen = False
                output.append(line)
                continue

            if in_default and re.match(r"^\s*use_system_font\s*=", line):
                output.append("    use_system_font = False")
                system_font_seen = True
                continue

            if in_default and re.match(r"^\s*font\s*=", line):
                output.append("    font = MesloLGS NF Regular 11")
                font_seen = True
                continue

            output.append(line)

        if in_default:
            finish_default()
        if in_profiles and not default_seen:
            output.extend([
                "  [[default]]",
                "    use_system_font = False",
                "    font = MesloLGS NF Regular 11",
            ])
        if not profiles_seen:
            if output and output[-1].strip():
                output.append("")
            output.extend([
                "[profiles]",
                "  [[default]]",
                "    use_system_font = False",
                "    font = MesloLGS NF Regular 11",
            ])

        return output

    async def configure_default_terminal(self) -> None:
        """Make Terminator the system x-terminal-emulator alternative."""
        terminator = shutil.which("terminator")
        if not terminator:
            raise RuntimeError("Terminator was not found after package installation.")

        await ProcessStream(name="Atlas.Terminator.Default")(
            f"sudo update-alternatives --set x-terminal-emulator {shlex.quote(terminator)}"
        )

    async def configure_gnome_terminal(self) -> None:
        """Keep GNOME Terminal usable with MesloLGS NF as a fallback terminal."""
        if not os.environ.get("DISPLAY"):
            return

        try:
            result = await Process(name="Atlas.GnomeTerminal.Profile")(
                "gsettings get org.gnome.Terminal.ProfilesList default"
            )
        except ProcessError:
            return

        profile = result.stdout.strip().strip("'")
        if not profile:
            return

        schema = (
            "org.gnome.Terminal.Legacy.Profile:"
            f"/org/gnome/terminal/legacy/profiles:/:{profile}/"
        )
        command = (
            f"gsettings set {shlex.quote(schema)} use-system-font false && "
            f"gsettings set {shlex.quote(schema)} font {shlex.quote('MesloLGS NF Regular 11')} && "
            f"gsettings set {shlex.quote(schema)} cell-width-scale 1.0 && "
            f"gsettings set {shlex.quote(schema)} cell-height-scale 1.0"
        )

        try:
            await ProcessStream(name="Atlas.GnomeTerminal.Font")(command)
        except ProcessError:
            log.warning("MesloLGS NF is installed, but GNOME Terminal font selection could not be changed automatically.")

    async def configure_login_shell(self) -> None:
        """Set Zsh as the current user's login shell when necessary."""
        zsh = Path("/usr/bin/zsh")
        if not zsh.is_file():
            raise RuntimeError("/usr/bin/zsh was not found after package installation.")

        user = os.environ.get("USER")
        if not user:
            raise RuntimeError("USER is not set; cannot change the login shell safely.")

        try:
            result = await Process(name="Atlas.LoginShell")(
                f"getent passwd {shlex.quote(user)} | cut -d: -f7"
            )
            if result.stdout.strip() == str(zsh):
                return
        except ProcessError:
            pass

        await ProcessStream(name="Atlas.LoginShell.Set")(
            f"sudo chsh -s {shlex.quote(str(zsh))} {shlex.quote(user)}"
        )

    async def setup(self) -> None:
        """Configure a polished, reproducible interactive environment for an Atlas node."""
        await self.install_packages()
        await self.install_oh_my_zsh()
        await self.install_powerlevel10k()
        await self.install_fonts()
        self.configure_zshrc()
        self.configure_terminator()
        await self.configure_default_terminal()
        await self.configure_gnome_terminal()
        await self.configure_login_shell()

        log.info("Oh My Zsh + Powerlevel10k + Terminator setup complete.")
        log.info("Open Terminator or run `exec zsh`, then run `p10k configure` to choose the prompt style.")
