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


def test_html_board_size_is_fixed_in_css() -> None:
    css = (WEB / "styles.css").read_text(encoding="utf-8")

    assert "--board-size: 640px" in css
    assert "--square-size: 80px" in css
    assert "width: var(--board-size)" in css
    assert "height: var(--board-size)" in css
    assert "grid-template-columns: repeat(8, var(--square-size))" in css
    assert "aspect-ratio" not in css
    assert "font-size: clamp" not in css
    assert ".app-shell { grid-template-columns: 1fr" not in css


def test_web_revive_ui_has_counters_and_check_lockout() -> None:
    game_js = (WEB / "game.js").read_text(encoding="utf-8")
    css = (WEB / "styles.css").read_text(encoding="utf-8")

    assert "if (this.inCheck(color)) return []" in game_js
    assert "updateReviveButtons" in game_js
    assert "renderReviveMeter" in game_js
    assert "REVIVE_COUNTER_LIMIT" in game_js
    assert "남은 ${remaining}" in game_js
    assert "button.disabled = exhausted || inCheck" in game_js
    assert ".revive-buttons button.spent" in css
    assert ".meter-circle.used" in css


def test_web_uses_shared_five_count_revive_system() -> None:
    data = (WEB / "ai-data.js").read_text(encoding="utf-8")
    html = (WEB / "index.html").read_text(encoding="utf-8")

    assert "reviveCounterLimit: 5" in data
    assert "reviveCosts: { P: 1, N: 2, Q: 3, R: 3 }" in data
    assert "reviveLimits" not in data
    assert 'data-revive="Q"' in html
    assert 'data-revive="B"' not in html
