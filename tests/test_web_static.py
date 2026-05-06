from pathlib import Path

ROOT = Path(__file__).parents[1]
WEB = ROOT / "web"


def test_html_uses_local_scripts_without_network_dependencies() -> None:
    html = (WEB / "index.html").read_text(encoding="utf-8")

    assert 'src="ai-data.js"' in html
    assert 'src="game.js"' in html
    assert "https://" not in html
    assert "http://" not in html


def test_browser_game_has_local_data_and_computer_label() -> None:
    data = (WEB / "ai-data.js").read_text(encoding="utf-8")
    game = (WEB / "game.js").read_text(encoding="utf-8")

    assert "window.REVIVE_CHESS_AI_DATA" in data
    assert "COMPUTER" in game
    assert "COMPU" + "TOR" not in game
    assert "class ChessGame" in game
    assert "class ComputerPlayer" in game
