from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Iterable

FILES = "abcdefgh"
PROMOTION_PIECE = "Q"
CAPTURE_POINTS = {"P": 1, "N": 3, "B": 5, "R": 5, "Q": 0, "K": 0}
REVIVE_COUNTER_LIMIT = 5
REVIVE_COSTS = {"P": 1, "N": 2, "Q": 3, "R": 3}
UNICODE_PIECES = {
    "wK": "♔", "wQ": "♕", "wR": "♖", "wB": "♗", "wN": "♘", "wP": "♙",
    "bK": "♚", "bQ": "♛", "bR": "♜", "bB": "♝", "bN": "♞", "bP": "♟",
}


@dataclass(frozen=True)
class Move:
    start: tuple[int, int]
    end: tuple[int, int]
    promotion: str | None = None
    is_castling: bool = False
    is_en_passant: bool = False

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
    revives_used: dict[str, int] = field(default_factory=lambda: {"w": 0, "b": 0})
    castling_rights: dict[str, dict[str, bool]] = field(
        default_factory=lambda: {"w": {"K": True, "Q": True}, "b": {"K": True, "Q": True}}
    )
    en_passant_target: tuple[int, int] | None = None
    halfmove_clock: int = 0
    fullmove_number: int = 1
    position_counts: dict[str, int] = field(default_factory=dict)
    move_log: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.board:
            self.board = initial_board()
        if not self.position_counts:
            self.position_counts[self.position_key()] = 1

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
        if self.in_check(color):
            return []
        square = self.revive_square(color)
        if square is None or self.board[square[0]][square[1]] is not None:
            return []
        actions: list[ReviveAction] = []
        for piece in ("P", "N", "Q", "R"):
            if self.can_revive(color, piece):
                trial = self.clone()
                trial._apply_revive_no_validation(piece, color)
                if not trial.in_check(color):
                    actions.append(ReviveAction(color, piece, square))
        return actions

    def can_revive(self, color: str, piece: str) -> bool:
        if piece not in REVIVE_COSTS or piece not in self.captured[color]:
            return False
        return self.revives_used[color] + REVIVE_COSTS[piece] <= REVIVE_COUNTER_LIMIT

    def make_move(self, move: Move) -> None:
        legal = {candidate.uci(): candidate for candidate in self.legal_moves(self.turn)}
        if move.uci() not in legal:
            raise ValueError("Illegal move")
        self._apply_move_no_validation(legal[move.uci()])
        self.turn = opposite(self.turn)
        self._finish_turn()

    def revive(self, piece: str) -> ReviveAction:
        actions = {action.piece: action for action in self.legal_revives(self.turn)}
        if piece not in actions:
            raise ValueError("Illegal revive")
        action = self._apply_revive_no_validation(piece, self.turn)
        self.turn = opposite(self.turn)
        self._finish_turn()
        return action

    def status(self) -> str:
        if self.is_fifty_move_draw():
            return "Draw: 50-move rule"
        if self.is_threefold_repetition():
            return "Draw: threefold repetition"
        if self.in_check(self.turn):
            if not self.legal_moves(self.turn) and not self.legal_revives(self.turn):
                return f"Checkmate: {'White' if opposite(self.turn) == 'w' else 'Black'} wins"
            return "Check"
        if not self.legal_moves(self.turn) and not self.legal_revives(self.turn):
            return "Stalemate"
        return "Playing"

    def is_fifty_move_draw(self) -> bool:
        return self.halfmove_clock >= 100

    def is_threefold_repetition(self) -> bool:
        return self.position_counts.get(self.position_key(), 0) >= 3

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

    def position_key(self) -> str:
        board_state = "/".join("".join(piece or "--" for piece in row) for row in self.board)
        rights = "".join(
            color + side for color in ("w", "b") for side in ("K", "Q") if self.castling_rights[color][side]
        ) or "-"
        en_passant = square_name(*self.en_passant_target) if self.en_passant_target else "-"
        variant = (
            f"wp{self.points['w']}bp{self.points['b']}|"
            f"wc{''.join(sorted(self.captured['w']))}|bc{''.join(sorted(self.captured['b']))}|"
            f"wr{self.revives_used['w']}|br{self.revives_used['b']}"
        )
        return f"{board_state} {self.turn} {rights} {en_passant} {variant}"

    def _finish_turn(self) -> None:
        if self.turn == "w":
            self.fullmove_number += 1
        self.position_counts[self.position_key()] = self.position_counts.get(self.position_key(), 0) + 1

    def _apply_move_no_validation(self, move: Move) -> None:
        sr, sc = move.start
        er, ec = move.end
        piece = self.board[sr][sc]
        if piece is None:
            raise ValueError("No piece at start square")
        captured_square = (er, ec)
        if move.is_en_passant:
            captured_square = (sr, ec)
        captured_piece = self.board[captured_square[0]][captured_square[1]]

        self.board[sr][sc] = None
        if move.is_en_passant:
            self.board[captured_square[0]][captured_square[1]] = None

        placed = piece
        if piece[1] == "P" and er in {0, 7}:
            placed = piece[0] + (move.promotion or PROMOTION_PIECE)
        self.board[er][ec] = placed

        if move.is_castling:
            rook_start_col, rook_end_col = (7, 5) if ec == 6 else (0, 3)
            rook = self.board[sr][rook_start_col]
            self.board[sr][rook_start_col] = None
            self.board[sr][rook_end_col] = rook

        self._update_castling_rights(piece, move.start, captured_piece, captured_square)
        self.en_passant_target = None
        if piece[1] == "P" and abs(er - sr) == 2:
            self.en_passant_target = ((sr + er) // 2, sc)

        if captured_piece:
            mover = piece[0]
            captured_color, captured_type = captured_piece[0], captured_piece[1]
            self.points[mover] += CAPTURE_POINTS[captured_type]
            self.captured[captured_color].append(captured_type)
            marker = " e.p." if move.is_en_passant else ""
            self.move_log.append(f"{piece}@{square_name(sr, sc)}x{captured_piece}@{square_name(*captured_square)}{marker}")
        else:
            castle = " castle" if move.is_castling else ""
            self.move_log.append(f"{piece}@{square_name(sr, sc)}-{square_name(er, ec)}{castle}")

        self.halfmove_clock = 0 if piece[1] == "P" or captured_piece else self.halfmove_clock + 1

    def _update_castling_rights(
        self,
        piece: str,
        start: tuple[int, int],
        captured_piece: str | None,
        captured_square: tuple[int, int],
    ) -> None:
        color, kind = piece[0], piece[1]
        if kind == "K":
            self.castling_rights[color]["K"] = False
            self.castling_rights[color]["Q"] = False
        elif kind == "R":
            if start == home_rook_square(color, "K"):
                self.castling_rights[color]["K"] = False
            elif start == home_rook_square(color, "Q"):
                self.castling_rights[color]["Q"] = False
        if captured_piece and captured_piece[1] == "R":
            captured_color = captured_piece[0]
            if captured_square == home_rook_square(captured_color, "K"):
                self.castling_rights[captured_color]["K"] = False
            elif captured_square == home_rook_square(captured_color, "Q"):
                self.castling_rights[captured_color]["Q"] = False

    def _apply_revive_no_validation(self, piece: str, color: str) -> ReviveAction:
        square = self.revive_square(color)
        if square is None:
            raise ValueError("No revive square")
        r, c = square
        self.board[r][c] = color + piece
        self.captured[color].remove(piece)
        self.revives_used[color] += REVIVE_COSTS[piece]
        self.en_passant_target = None
        self.halfmove_clock += 1
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
                if r == start_row and in_bounds(nnr, c) and self.board[nnr][c] is None:
                    moves.append(Move((r, c), (nnr, c)))
            for dc in (-1, 1):
                nr, nc = r + direction, c + dc
                if in_bounds(nr, nc) and self.board[nr][nc] and self.board[nr][nc][0] == enemy and self.board[nr][nc][1] != "K":
                    moves.append(Move((r, c), (nr, nc), PROMOTION_PIECE if nr in {0, 7} else None))
                if self.en_passant_target == (nr, nc):
                    captured = self.board[r][nc] if in_bounds(r, nc) else None
                    if captured == enemy + "P":
                        moves.append(Move((r, c), (nr, nc), is_en_passant=True))
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
            moves.extend(self._castling_moves(color, r, c))
        return moves

    def _castling_moves(self, color: str, r: int, c: int) -> list[Move]:
        if self.in_check(color) or (r, c) != home_king_square(color):
            return []
        moves: list[Move] = []
        for side, king_end_col, between, safe_cols in (
            ("K", 6, (5, 6), (5, 6)),
            ("Q", 2, (1, 2, 3), (3, 2)),
        ):
            if not self.castling_rights[color][side]:
                continue
            rook_square = home_rook_square(color, side)
            if self.board[rook_square[0]][rook_square[1]] != color + "R":
                continue
            if any(self.board[r][col] is not None for col in between):
                continue
            if any(self.square_attacked(r, col, opposite(color)) for col in safe_cols):
                continue
            moves.append(Move((r, c), (r, king_end_col), is_castling=True))
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


def home_king_square(color: str) -> tuple[int, int]:
    return (7, 4) if color == "w" else (0, 4)


def home_rook_square(color: str, side: str) -> tuple[int, int]:
    row = 7 if color == "w" else 0
    return (row, 7 if side == "K" else 0)


def square_name(row: int, col: int) -> str:
    return f"{FILES[col]}{8 - row}"


def parse_square(name: str) -> tuple[int, int]:
    return 8 - int(name[1]), FILES.index(name[0])
