from chess_variant.ai import ComputerPlayer
from chess_variant.game import ChessGame, Move, parse_square


def move(start: str, end: str) -> Move:
    return Move(parse_square(start), parse_square(end))


def empty_game() -> ChessGame:
    game = ChessGame()
    game.board = [[None] * 8 for _ in range(8)]
    game.points = {"w": 0, "b": 0}
    game.captured = {"w": [], "b": []}
    game.revives_used = {"w": 0, "b": 0}
    game.position_counts = {game.position_key(): 1}
    return game


def test_castling_moves_king_and_rook_and_clears_rights() -> None:
    game = empty_game()
    game.board[7][4] = "wK"
    game.board[7][7] = "wR"
    game.board[0][4] = "bK"

    legal = game.legal_moves("w")
    castle = next(candidate for candidate in legal if candidate.is_castling and candidate.end == parse_square("g1"))
    game.make_move(castle)

    assert game.board[7][6] == "wK"
    assert game.board[7][5] == "wR"
    assert game.board[7][4] is None
    assert game.board[7][7] is None
    assert game.castling_rights["w"] == {"K": False, "Q": False}


def test_castling_not_legal_through_attacked_square() -> None:
    game = empty_game()
    game.board[7][4] = "wK"
    game.board[7][7] = "wR"
    game.board[0][4] = "bK"
    game.board[0][5] = "bR"

    assert not any(candidate.is_castling for candidate in game.legal_moves("w"))


def test_en_passant_captures_pawn_and_awards_point() -> None:
    game = empty_game()
    game.board[7][4] = "wK"
    game.board[0][4] = "bK"
    game.board[3][4] = "wP"
    game.board[1][3] = "bP"
    game.turn = "b"
    game.position_counts = {game.position_key(): 1}

    game.make_move(move("d7", "d5"))
    en_passant = next(candidate for candidate in game.legal_moves("w") if candidate.is_en_passant)
    game.make_move(en_passant)

    assert game.board[2][3] == "wP"
    assert game.board[3][3] is None
    assert game.points["w"] == 1
    assert game.captured["b"] == ["P"]


def test_fifty_move_rule_draw() -> None:
    game = ChessGame()
    game.halfmove_clock = 100

    assert game.status() == "Draw: 50-move rule"


def test_threefold_repetition_draw() -> None:
    game = ChessGame()
    key = game.position_key()
    game.position_counts[key] = 3

    assert game.status() == "Draw: threefold repetition"


def test_computer_difficulties_choose_actions_and_can_select_castling() -> None:
    game = empty_game()
    game.board[7][4] = "wK"
    game.board[0][4] = "bK"
    game.board[0][7] = "bR"
    game.turn = "b"
    game.position_counts = {game.position_key(): 1}

    for difficulty in ("초급자", "중급자", "상급자"):
        computer = ComputerPlayer("b", difficulty=difficulty, seed=3)
        action = computer.choose_action(game)
        assert action.kind in {"move", "revive"}

    advanced = ComputerPlayer("b", difficulty="상급자", seed=1)
    castle_actions = [action for action in advanced.actions_for(game, "b") if action.move and action.move.is_castling]
    assert castle_actions
    assert advanced.choose_action(game).move and advanced.choose_action(game).move.is_castling
