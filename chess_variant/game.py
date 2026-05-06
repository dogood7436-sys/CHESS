from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Iterable

FILES = "abcdefgh"
PROMOTION_PIECE = "Q"
CAPTURE_POINTS = {"P": 1, "N": 3, "B": 5, "R": 5, "Q": 0, "K": 0}
REVIVE_COSTS = {"P": 2, "N": 6, "B": 10, "R": 10}
UNICODE_PIECES = {
    "wK": "♔", "wQ": "♕", "wR": "♖", "wB": "♗", "wN": "♘", "wP": "♙",
    "bK": "♚", "bQ": "♛", "bR": "♜", "bB": "♝", "bN": "♞", "bP": "♟",
}


@dataclass(frozen=True)
class Move:
    start: tuple[int, int]
    end: tuple[int, int]
    promotion: str | None = None

    def uci(self) -> str:
        return square_name(*self.start) + square_name(*self.end) + (self.promotion or "").lower()


@dataclass(frozen=True)
class ReviveAction:
    color: str
    piece: str
    square: tuple[int, int]


@dataclass
class ChessGame:
    board: list[list[str | None]] = field(default_factory=list)
    turn: str = "w"
    points: dict[str, int] = field(default_factory=lambda: {"w": 0, "b": 0})
    captured: dict[str, list[str]] = field(default_factory=lambda: {"w": [], "b": []})
    revives_used: dict[str, dict[str, int]] = field(
        default_factory=lambda: {"w": {"P": 0, "N": 0, "BR": 0}, "b": {"P": 0, "N": 0, "BR": 0}}
    )
    move_log: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.board:
            self.board = initial_board()

    def clone(self) -> "ChessGame":
        return deepcopy(self)

    def legal_moves(self, color: str | None = None) -> list[Move]:
        color = color or self.turn
        moves: list[Move] = []
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if piece and piece[0] == color:
                    for move in self._pseudo_moves(r, c):
                        trial = self.clone()
                        trial._apply_move_no_validation(move)
                        if not trial.in_check(color):
                            moves.append(move)
        return moves

    def legal_revives(self, color: str | None = None) -> list[ReviveAction]:
        color = color or self.turn
        square = self.revive_square(color)
        if square is None or self.board[square[0]][square[1]] is not None:
            return []
        actions: list[ReviveAction] = []
        for piece in ("P", "N", "B", "R"):
            if self.can_revive(color, piece):
                trial = self.clone()
                trial._apply_revive_no_validation(piece, color)
                if not trial.in_check(color):
                    actions.append(ReviveAction(color, piece, square))
        return actions

    def can_revive(self, color: str, piece: str) -> bool:
        if piece not in REVIVE_COSTS or piece not in self.captured[color]:
            return False
        if self.points[color] < REVIVE_COSTS[piece]:
            return False
        if piece == "P":
            return self.revives_used[color]["P"] < 2
        if piece == "N":
            return self.revives_used[color]["N"] < 1
        if piece in {"B", "R"}:
            return self.revives_used[color]["BR"] < 1
        return False

    def make_move(self, move: Move) -> None:
        if move not in self.legal_moves(self.turn):
            raise ValueError("Illegal move")
        self._apply_move_no_validation(move)
        self.turn = opposite(self.turn)

    def revive(self, piece: str) -> ReviveAction:
        actions = {action.piece: action for action in self.legal_revives(self.turn)}
        if piece not in actions:
            raise ValueError("Illegal revive")
        action = self._apply_revive_no_validation(piece, self.turn)
        self.turn = opposite(self.turn)
        return action

    def status(self) -> str:
        if self.in_check(self.turn):
            if not self.legal_moves(self.turn) and not self.legal_revives(self.turn):
                return f"Checkmate: {'White' if opposite(self.turn) == 'w' else 'Black'} wins"
            return "Check"
        if not self.legal_moves(self.turn) and not self.legal_revives(self.turn):
            return "Stalemate"
        return "Playing"

    def revive_square(self, color: str) -> tuple[int, int] | None:
        king = self.king_square(color)
        if king is None:
            return None
        direction = -1 if color == "w" else 1
        r, c = king[0] + direction, king[1]
        if in_bounds(r, c):
            return (r, c)
        return None

    def king_square(self, color: str) -> tuple[int, int] | None:
        target = color + "K"
        for r in range(8):
            for c in range(8):
                if self.board[r][c] == target:
                    return (r, c)
        return None

    def in_check(self, color: str) -> bool:
        king = self.king_square(color)
        if king is None:
            return True
        return self.square_attacked(king[0], king[1], opposite(color))

    def square_attacked(self, row: int, col: int, by_color: str) -> bool:
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if piece and piece[0] == by_color:
                    for ar, ac in self._attacks_from(r, c):
                        if (ar, ac) == (row, col):
                            return True
        return False

    def _apply_move_no_validation(self, move: Move) -> None:
        sr, sc = move.start
        er, ec = move.end
        piece = self.board[sr][sc]
        captured_piece = self.board[er][ec]
        if piece is None:
            raise ValueError("No piece at start square")
        self.board[sr][sc] = None
        placed = piece
        if piece[1] == "P" and er in {0, 7}:
            placed = piece[0] + (move.promotion or PROMOTION_PIECE)
        self.board[er][ec] = placed
        if captured_piece:
            mover = piece[0]
            captured_color, captured_type = captured_piece[0], captured_piece[1]
            self.points[mover] += CAPTURE_POINTS[captured_type]
            self.captured[captured_color].append(captured_type)
            self.move_log.append(f"{piece}@{square_name(sr, sc)}x{captured_piece}@{square_name(er, ec)}")
        else:
            self.move_log.append(f"{piece}@{square_name(sr, sc)}-{square_name(er, ec)}")

    def _apply_revive_no_validation(self, piece: str, color: str) -> ReviveAction:
        square = self.revive_square(color)
        if square is None:
            raise ValueError("No revive square")
        r, c = square
        self.board[r][c] = color + piece
        self.points[color] -= REVIVE_COSTS[piece]
        self.captured[color].remove(piece)
        if piece == "P":
            self.revives_used[color]["P"] += 1
        elif piece == "N":
            self.revives_used[color]["N"] += 1
        else:
            self.revives_used[color]["BR"] += 1
        self.move_log.append(f"{color}{piece} revived@{square_name(r, c)}")
        return ReviveAction(color, piece, square)

    def _pseudo_moves(self, r: int, c: int) -> Iterable[Move]:
        piece = self.board[r][c]
        if not piece:
            return []
        color, kind = piece[0], piece[1]
        enemy = opposite(color)
        moves: list[Move] = []
        if kind == "P":
            direction = -1 if color == "w" else 1
            start_row = 6 if color == "w" else 1
            nr = r + direction
            if in_bounds(nr, c) and self.board[nr][c] is None:
                moves.append(Move((r, c), (nr, c), PROMOTION_PIECE if nr in {0, 7} else None))
                nnr = r + 2 * direction
                if r == start_row and self.board[nnr][c] is None:
                    moves.append(Move((r, c), (nnr, c)))
            for dc in (-1, 1):
                nr, nc = r + direction, c + dc
                if in_bounds(nr, nc) and self.board[nr][nc] and self.board[nr][nc][0] == enemy and self.board[nr][nc][1] != "K":
                    moves.append(Move((r, c), (nr, nc), PROMOTION_PIECE if nr in {0, 7} else None))
        elif kind == "N":
            for dr, dc in ((-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)):
                add_if_valid(moves, self.board, color, r, c, r + dr, c + dc)
        elif kind in {"B", "R", "Q"}:
            directions = []
            if kind in {"B", "Q"}:
                directions += [(-1, -1), (-1, 1), (1, -1), (1, 1)]
            if kind in {"R", "Q"}:
                directions += [(-1, 0), (1, 0), (0, -1), (0, 1)]
            for dr, dc in directions:
                nr, nc = r + dr, c + dc
                while in_bounds(nr, nc):
                    target = self.board[nr][nc]
                    if target is None:
                        moves.append(Move((r, c), (nr, nc)))
                    else:
                        if target[0] != color and target[1] != "K":
                            moves.append(Move((r, c), (nr, nc)))
                        break
                    nr += dr
                    nc += dc
        elif kind == "K":
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr or dc:
                        add_if_valid(moves, self.board, color, r, c, r + dr, c + dc)
        return moves

    def _attacks_from(self, r: int, c: int) -> Iterable[tuple[int, int]]:
        piece = self.board[r][c]
        if not piece:
            return []
        color, kind = piece[0], piece[1]
        attacks: list[tuple[int, int]] = []
        if kind == "P":
            direction = -1 if color == "w" else 1
            for dc in (-1, 1):
                nr, nc = r + direction, c + dc
                if in_bounds(nr, nc):
                    attacks.append((nr, nc))
        elif kind == "N":
            for dr, dc in ((-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)):
                if in_bounds(r + dr, c + dc):
                    attacks.append((r + dr, c + dc))
        elif kind in {"B", "R", "Q"}:
            directions = []
            if kind in {"B", "Q"}:
                directions += [(-1, -1), (-1, 1), (1, -1), (1, 1)]
            if kind in {"R", "Q"}:
                directions += [(-1, 0), (1, 0), (0, -1), (0, 1)]
            for dr, dc in directions:
                nr, nc = r + dr, c + dc
                while in_bounds(nr, nc):
                    attacks.append((nr, nc))
                    if self.board[nr][nc] is not None:
                        break
                    nr += dr
                    nc += dc
        elif kind == "K":
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if (dr or dc) and in_bounds(r + dr, c + dc):
                        attacks.append((r + dr, c + dc))
        return attacks


def initial_board() -> list[list[str | None]]:
    return [
        ["bR", "bN", "bB", "bQ", "bK", "bB", "bN", "bR"],
        ["bP"] * 8,
        [None] * 8,
        [None] * 8,
        [None] * 8,
        [None] * 8,
        ["wP"] * 8,
        ["wR", "wN", "wB", "wQ", "wK", "wB", "wN", "wR"],
    ]


def opposite(color: str) -> str:
    return "b" if color == "w" else "w"


def in_bounds(r: int, c: int) -> bool:
    return 0 <= r < 8 and 0 <= c < 8


def add_if_valid(moves: list[Move], board: list[list[str | None]], color: str, sr: int, sc: int, er: int, ec: int) -> None:
    if not in_bounds(er, ec):
        return
    target = board[er][ec]
    if target is None or (target[0] != color and target[1] != "K"):
        moves.append(Move((sr, sc), (er, ec)))


def square_name(row: int, col: int) -> str:
    return f"{FILES[col]}{8 - row}"


def parse_square(name: str) -> tuple[int, int]:
    return 8 - int(name[1]), FILES.index(name[0])
