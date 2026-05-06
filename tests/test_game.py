from chess_variant.ai import ComputerPlayer
from chess_variant.game import ChessGame, Move, parse_square


def move(start: str, end: str) -> Move:
    return Move(parse_square(start), parse_square(end))


def test_capture_awards_points_and_records_captured_piece() -> None:
    game = ChessGame()
    game.make_move(move("e2", "e4"))
    game.make_move(move("d7", "d5"))
    game.make_move(move("e4", "d5"))

    assert game.points["w"] == 1
    assert game.captured["b"] == ["P"]


def test_pawn_revives_in_front_of_own_king_and_consumes_limits() -> None:
    game = ChessGame()
    game.board[6][4] = None
    game.points["w"] = 4
    game.captured["w"] = ["P", "P"]

    action = game.revive("P")

    assert action.square == parse_square("e2")
    assert game.board[action.square[0]][action.square[1]] == "wP"
    assert game.points["w"] == 2
    assert game.revives_used["w"]["P"] == 1
    assert game.turn == "b"


def test_bishop_and_rook_share_one_revive_limit() -> None:
    game = ChessGame()
    game.board[6][4] = None
    game.points["w"] = 20
    game.captured["w"] = ["B", "R"]
    game.revive("B")
    game.turn = "w"
    game.board[6][4] = None

    assert not game.can_revive("w", "R")


def test_queen_cannot_be_revived() -> None:
    game = ChessGame()
    game.points["w"] = 99
    game.captured["w"] = ["Q"]

    assert all(action.piece != "Q" for action in game.legal_revives("w"))


def test_computer_selects_local_action() -> None:
    game = ChessGame()
    computer = ComputerPlayer("b", seed=1)
    action = computer.choose_action(game)

    assert action.kind in {"move", "revive"}
