from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

from .game import ChessGame, Move, ReviveAction, opposite

DATA_PATH = Path(__file__).with_name("ai_data.json")


@dataclass(frozen=True)
class ComputerAction:
    kind: str
    move: Move | None = None
    revive: ReviveAction | None = None
    score: int = 0


class ComputerPlayer:
    """Offline computer opponent driven by bundled chess-evaluation data."""

    def __init__(self, color: str, seed: int | None = None) -> None:
        self.color = color
        self.random = random.Random(seed)
        self.data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        self.material: dict[str, int] = self.data["material"]
        self.piece_square: dict[str, list[int]] = self.data["piece_square"]
        self.opening_moves: set[str] = set(self.data["opening_moves"])

    def choose_action(self, game: ChessGame) -> ComputerAction:
        candidates: list[ComputerAction] = []
        for move in game.legal_moves(self.color):
            trial = game.clone()
            trial._apply_move_no_validation(move)
            score = self.evaluate(trial)
            if move.uci()[:4] in self.opening_moves and len(game.move_log) < 8:
                score += 25
            candidates.append(ComputerAction("move", move=move, score=score))
        for revive in game.legal_revives(self.color):
            trial = game.clone()
            trial._apply_revive_no_validation(revive.piece, self.color)
            score = self.evaluate(trial) + self.revive_bonus(revive.piece)
            candidates.append(ComputerAction("revive", revive=revive, score=score))
        if not candidates:
            return ComputerAction("none", score=-999999)
        best_score = max(action.score for action in candidates)
        best = [action for action in candidates if action.score == best_score]
        return self.random.choice(best)

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
        return score

    def square_value(self, kind: str, color: str, row: int, col: int) -> int:
        table = self.piece_square.get(kind, [0] * 64)
        index = row * 8 + col if color == "w" else (7 - row) * 8 + col
        return table[index]

    def revive_bonus(self, piece: str) -> int:
        return {"P": 60, "N": 130, "B": 150, "R": 170}.get(piece, 0)
