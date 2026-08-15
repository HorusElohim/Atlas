from pathlib import Path

from atlas.ohmyzsh import OhMyZsh


def test_configure_zshrc_preserves_content_and_is_idempotent(tmp_path: Path) -> None:
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text(
        'export EDITOR="vim"\n'
        'export ZSH="$HOME/.oh-my-zsh"\n'
        "plugins=(git)\n"
        "source $ZSH/oh-my-zsh.sh\n"
        'ZSH_THEME="robbyrussell"\n',
        encoding="utf-8",
    )

    setup = OhMyZsh(name="TestOhMyZsh", home=tmp_path)
    setup.configure_zshrc()
    setup.configure_zshrc()

    content = zshrc.read_text(encoding="utf-8")

    assert 'export EDITOR="vim"' in content
    assert "plugins=(git)" in content
    assert content.count('export PATH="$HOME/.local/bin:$PATH"') == 1
    assert content.count('ZSH_THEME="powerlevel10k/powerlevel10k"') == 1
    assert content.count('[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh') == 1
    assert content.index('ZSH_THEME="powerlevel10k/powerlevel10k"') < content.index("source $ZSH/oh-my-zsh.sh")


def test_configure_zshrc_adds_minimal_oh_my_zsh_wiring(tmp_path: Path) -> None:
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text('export EDITOR="nano"\n', encoding="utf-8")

    OhMyZsh(name="TestOhMyZsh", home=tmp_path).configure_zshrc()

    content = zshrc.read_text(encoding="utf-8")

    assert 'export PATH="$HOME/.local/bin:$PATH"' in content
    assert 'export ZSH="$HOME/.oh-my-zsh"' in content
    assert 'ZSH_THEME="powerlevel10k/powerlevel10k"' in content
    assert "source $ZSH/oh-my-zsh.sh" in content


def test_configure_zshrc_keeps_existing_local_bin_path(tmp_path: Path) -> None:
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text('export PATH="$HOME/.local/bin:/opt/bin:$PATH"\n', encoding="utf-8")

    OhMyZsh(name="TestOhMyZsh", home=tmp_path).configure_zshrc()

    content = zshrc.read_text(encoding="utf-8")
    assert content.count("$HOME/.local/bin") == 1


def test_configure_terminator_creates_default_meslo_profile(tmp_path: Path) -> None:
    setup = OhMyZsh(name="TestOhMyZsh", home=tmp_path)
    setup.configure_terminator()

    content = setup.terminator_config.read_text(encoding="utf-8")
    assert "[profiles]" in content
    assert "[[default]]" in content
    assert "use_system_font = False" in content
    assert "font = MesloLGS NF Regular 11" in content


def test_configure_terminator_preserves_other_profile_options(tmp_path: Path) -> None:
    config = tmp_path / ".config" / "terminator" / "config"
    config.parent.mkdir(parents=True)
    config.write_text(
        "[global_config]\n"
        "[profiles]\n"
        "  [[default]]\n"
        "    background_color = #101010\n"
        "    use_system_font = True\n"
        "    font = Monospace 10\n"
        "[plugins]\n",
        encoding="utf-8",
    )

    setup = OhMyZsh(name="TestOhMyZsh", home=tmp_path)
    setup.configure_terminator()
    setup.configure_terminator()

    content = config.read_text(encoding="utf-8")
    assert "background_color = #101010" in content
    assert content.count("use_system_font = False") == 1
    assert content.count("font = MesloLGS NF Regular 11") == 1
