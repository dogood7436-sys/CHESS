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


def test_pawn_revives_in_front_of_own_king_and_consumes_one_count() -> None:
    game = ChessGame()
    game.board[6][4] = None
    game.captured["w"] = ["P"]

    action = game.revive("P")

    assert action.square == parse_square("e2")
    assert game.board[action.square[0]][action.square[1]] == "wP"
    assert game.points["w"] == 0
    assert game.revives_used["w"] == 1
    assert game.turn == "b"


def test_shared_five_count_revive_meter_blocks_overflow() -> None:
    game = ChessGame()
    game.board[6][4] = None
    game.captured["w"] = ["B", "N", "P"]
    game.revive("B")
    game.turn = "w"
    game.board[6][4] = None
    game.revive("N")
    game.turn = "w"
    game.board[6][4] = None

    assert game.revives_used["w"] == 5
    assert not game.can_revive("w", "P")


def test_same_piece_can_revive_repeatedly_when_counter_allows() -> None:
    game = ChessGame()
    game.board[6][4] = None
    game.captured["w"] = ["N", "N"]

    first = game.revive("N")
    game.turn = "w"
    game.board[6][4] = None
    second = game.revive("N")

    assert first.piece == second.piece == "N"
    assert game.revives_used["w"] == 4
    assert game.captured["w"] == []


def test_rook_uses_three_count_and_queen_cannot_be_revived() -> None:
    game = ChessGame()
    game.board[6][4] = None
    game.captured["w"] = ["R", "Q"]

    game.revive("R")

    assert game.revives_used["w"] == 3
    assert not game.can_revive("w", "Q")
    assert all(action.piece != "Q" for action in game.legal_revives("w"))


def test_computer_selects_local_action() -> None:
    game = ChessGame()
    computer = ComputerPlayer("b", seed=1)
    action = computer.choose_action(game)

    assert action.kind in {"move", "revive"}


def test_revive_is_not_allowed_while_in_check() -> None:
    game = ChessGame()
    game.board = [[None] * 8 for _ in range(8)]
    game.board[7][4] = "wK"
    game.board[0][0] = "bK"
    game.board[0][4] = "bR"
    game.captured["w"] = ["P"]
    game.position_counts = {game.position_key(): 1}

    assert game.in_check("w")
    assert game.legal_revives("w") == []
