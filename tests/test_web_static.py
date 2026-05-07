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
    assert "ornate-board-frame" in css
    assert "radial-gradient(circle at 50% 42%" in css
    assert ".meter-circle.used" in css


def test_web_uses_shared_five_count_revive_system() -> None:
    data = (WEB / "ai-data.js").read_text(encoding="utf-8")
    html = (WEB / "index.html").read_text(encoding="utf-8")

    assert "reviveCounterLimit: 5" in data
    assert "Q: 20" in data
    assert "reviveCosts: { P: 1, N: 2, B: 3, R: 3 }" in data
    assert "reviveLimits" not in data
    assert 'data-revive="B"' in html
    assert 'data-revive="Q"' not in html


def test_web_has_requested_hidden_skill_cards_and_kill_point_reward() -> None:
    game_js = (WEB / "game.js").read_text(encoding="utf-8")
    html = (WEB / "index.html").read_text(encoding="utf-8")

    assert game_js.count("id: '") == 5
    for card_id in [
        "valiant_warrior",
        "iron_empress",
        "knight_king",
        "trickster",
        "destroyer_chariot",
    ]:
        assert card_id in game_js
    for removed_card_id in ["wedge_charge", "brilliant_scheme", "wicked_scheme"]:
        assert removed_card_id not in game_js
    assert "type: '액티브'" in game_js
    assert "type: '패시브'" not in game_js
    assert "1회 사용 가능" in game_js
    assert "3턴마다 사용 가능" not in game_js
    assert "maybeAwardSkillCard" in game_js
    assert "this.points[color] >= 20" in game_js
    assert "cardSlots" in game_js
    assert "비공개" in game_js
    assert "cardButtons" in game_js
    assert "selectedCardsFromUi" not in game_js
    assert "pawn_forward_strike" not in game_js
    assert "supply_pawn" not in game_js
    assert "activateCard" in game_js
    assert "class AudioManager" in game_js
    assert "updateBgm(totalPoints)" in game_js
    assert "play(kind)" in game_js
    assert 'id="whiteCard"' not in html
    assert 'id="blackCard"' not in html
    assert 'id="cardButtons"' in html
    assert "킬 포인트" in html
    assert "랜덤으로 지급" in html
    assert 'id="enableSound"' in html
