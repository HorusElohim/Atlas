from pathlib import Path

from atlas.ohmyzsh import OhMyZsh


def test_configure_zshrc_preserves_content_and_is_idempotent(tmp_path: Path) -> None:
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text(
        'export EDITOR="vim"\nZSH_THEME="robbyrussell"\nplugins=(git)\n',
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
