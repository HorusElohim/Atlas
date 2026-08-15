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
    assert content.count('ZSH_THEME="powerlevel10k/powerlevel10k"') == 1
    assert content.count('[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh') == 1
    assert content.index('ZSH_THEME="powerlevel10k/powerlevel10k"') < content.index("source $ZSH/oh-my-zsh.sh")


def test_configure_zshrc_adds_minimal_oh_my_zsh_wiring(tmp_path: Path) -> None:
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text('export EDITOR="nano"\n', encoding="utf-8")

    OhMyZsh(name="TestOhMyZsh", home=tmp_path).configure_zshrc()

    content = zshrc.read_text(encoding="utf-8")

    assert 'export ZSH="$HOME/.oh-my-zsh"' in content
    assert 'ZSH_THEME="powerlevel10k/powerlevel10k"' in content
    assert "source $ZSH/oh-my-zsh.sh" in content
