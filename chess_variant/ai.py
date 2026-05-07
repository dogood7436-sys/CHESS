from __future__ import annotations

import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path

from .game import ChessGame, Move, ReviveAction, opposite

DATA_FILENAME = "ai_data.json"
DIFFICULTIES = ("초급자", "중급자", "상급자")


@dataclass(frozen=True)
class ComputerAction:
    kind: str
    move: Move | None = None
    revive: ReviveAction | None = None
    score: int = 0


class ComputerPlayer:
    """Offline computer opponent driven by bundled chess-evaluation data."""

    def __init__(self, color: str, difficulty: str = "중급자", seed: int | None = None) -> None:
        self.color = color
        self.difficulty = difficulty if difficulty in DIFFICULTIES else "중급자"
        self.random = random.Random(seed)
        self.data = json.loads(ai_data_path().read_text(encoding="utf-8"))
        self.material: dict[str, int] = self.data["material"]
        self.piece_square: dict[str, list[int]] = self.data["piece_square"]
        self.opening_moves: set[str] = set(self.data["opening_moves"])

    def choose_action(self, game: ChessGame) -> ComputerAction:
        candidates = self.actions_for(game, self.color)
        if not candidates:
            return ComputerAction("none", score=-999999)
        if self.difficulty == "초급자":
            return self.random.choice(candidates)
        if self.difficulty == "상급자":
            return self.choose_advanced(game, candidates)
        return self.choose_intermediate(game, candidates)

    def choose_intermediate(self, game: ChessGame, candidates: list[ComputerAction]) -> ComputerAction:
        scored = [self.score_action(game, action) for action in candidates]
        top_score = max(action.score for action in scored)
        top_band = [action for action in scored if action.score >= top_score - 30]
        return self.random.choice(top_band)

    def choose_advanced(self, game: ChessGame, candidates: list[ComputerAction]) -> ComputerAction:
        scored: list[ComputerAction] = []
        for action in candidates:
            trial = self.apply_action(game, action)
            score = self.minimax(trial, depth=2, maximizing=trial.turn == self.color, alpha=-999999, beta=999999)
            score += self.special_move_bonus(action)
            scored.append(self.with_score(action, score))
        best_score = max(action.score for action in scored)
        return self.random.choice([action for action in scored if action.score == best_score])

    def minimax(self, game: ChessGame, depth: int, maximizing: bool, alpha: int, beta: int) -> int:
        status = game.status()
        if depth == 0 or status not in {"Playing", "Check"}:
            return self.terminal_score(game, status)
        actions = self.actions_for(game, game.turn)
        if not actions:
            return self.terminal_score(game, status)
        if maximizing:
            value = -999999
            for action in actions:
                value = max(value, self.minimax(self.apply_action(game, action), depth - 1, False, alpha, beta))
                alpha = max(alpha, value)
                if beta <= alpha:
                    break
            return value
        value = 999999
        for action in actions:
            value = min(value, self.minimax(self.apply_action(game, action), depth - 1, True, alpha, beta))
            beta = min(beta, value)
            if beta <= alpha:
                break
        return value

    def terminal_score(self, game: ChessGame, status: str) -> int:
        if status.startswith("Checkmate"):
            winner = opposite(game.turn)
            return 999999 if winner == self.color else -999999
        if status.startswith("Draw") or status == "Stalemate":
            return 0
        return self.evaluate(game)

    def actions_for(self, game: ChessGame, color: str) -> list[ComputerAction]:
        actions = [ComputerAction("move", move=move) for move in game.legal_moves(color)]
        actions.extend(ComputerAction("revive", revive=revive) for revive in game.legal_revives(color))
        return actions

    def score_action(self, game: ChessGame, action: ComputerAction) -> ComputerAction:
        trial = self.apply_action(game, action)
        score = self.evaluate(trial) + self.special_move_bonus(action)
        if action.move and action.move.uci()[:4] in self.opening_moves and len(game.move_log) < 8:
            score += 25
        if self.difficulty == "중급자":
            score += self.random.randint(-15, 15)
        return self.with_score(action, score)

    def apply_action(self, game: ChessGame, action: ComputerAction) -> ChessGame:
        trial = game.clone()
        if action.kind == "move" and action.move:
            piece = trial.board[action.move.start[0]][action.move.start[1]]
            if piece is None:
                return trial
            mover = piece[0]
            trial._apply_move_no_validation(action.move)
            trial.turn = opposite(mover)
            trial._finish_turn()
        elif action.kind == "revive" and action.revive:
            trial._apply_revive_no_validation(action.revive.piece, action.revive.color)
            trial.turn = opposite(action.revive.color)
            trial._finish_turn()
        return trial

    def with_score(self, action: ComputerAction, score: int) -> ComputerAction:
        return ComputerAction(action.kind, action.move, action.revive, score)

    def special_move_bonus(self, action: ComputerAction) -> int:
        if action.kind == "revive" and action.revive:
            return self.revive_bonus(action.revive.piece)
        if action.move and action.move.is_castling:
            return 90
        if action.move and action.move.is_en_passant:
            return 45
        return 0

    def evaluate(self, game: ChessGame) -> int:
        score = 0
        for r, row in enumerate(game.board):
            for c, piece in enumerate(row):
                if not piece:
                    continue
                color, kind = piece[0], piece[1]
                value = self.material[kind] + self.square_value(kind, color, r, c)
                score += value if color == self.color else -value
        score += (game.points[self.color] - game.points[opposite(self.color)]) * 35
        if game.in_check(opposite(self.color)):
            score += 40
        if game.in_check(self.color):
            score -= 80
        if game.is_fifty_move_draw() or game.is_threefold_repetition():
            score = min(score, 0) if score > 0 else max(score, 0)
        return score

    def square_value(self, kind: str, color: str, row: int, col: int) -> int:
        table = self.piece_square.get(kind, [0] * 64)
        index = row * 8 + col if color == "w" else (7 - row) * 8 + col
        return table[index]

    def revive_bonus(self, piece: str) -> int:
        return {"P": 60, "N": 130, "B": 150, "R": 170}.get(piece, 0)


def ai_data_path() -> Path:
    bundled_root = getattr(sys, "_MEIPASS", None)
    if bundled_root:
        bundled_path = Path(bundled_root) / "chess_variant" / DATA_FILENAME
        if bundled_path.exists():
            return bundled_path
    return Path(__file__).with_name(DATA_FILENAME)
