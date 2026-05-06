from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .ai import ComputerPlayer
from .game import ChessGame, Move, REVIVE_COSTS, UNICODE_PIECES, opposite, square_name

LIGHT = "#f0d9b5"
DARK = "#b58863"
SELECTED = "#f7ec6e"
LEGAL = "#9bd67d"
WHITE = "w"
BLACK = "b"


class ChessVariantApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Revive Chess")
        self.resizable(False, False)
        self.game = ChessGame()
        self.selected: tuple[int, int] | None = None
        self.legal_targets: dict[tuple[int, int], Move] = {}
        self.opponent_var = tk.StringVar(value="COMPUTOR")
        self.human_color = WHITE
        self.computer: ComputerPlayer | None = ComputerPlayer(BLACK)
        self.buttons: list[list[tk.Button]] = []
        self.status_var = tk.StringVar()
        self.points_var = tk.StringVar()
        self.captured_var = tk.StringVar()
        self._build_layout()
        self.refresh()

    def _build_layout(self) -> None:
        root = ttk.Frame(self, padding=10)
        root.grid(row=0, column=0)
        board_frame = ttk.Frame(root)
        board_frame.grid(row=0, column=0)
        for r in range(8):
            row: list[tk.Button] = []
            for c in range(8):
                button = tk.Button(
                    board_frame,
                    width=4,
                    height=2,
                    font=("Segoe UI Symbol", 24),
                    command=lambda rr=r, cc=c: self.on_square(rr, cc),
                )
                button.grid(row=r, column=c)
                row.append(button)
            self.buttons.append(row)

        side = ttk.Frame(root, padding=(12, 0, 0, 0))
        side.grid(row=0, column=1, sticky="n")
        ttk.Label(side, text="상대 선택").grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(side, text="USER", variable=self.opponent_var, value="USER", command=self.new_game).grid(row=1, column=0, sticky="w")
        ttk.Radiobutton(side, text="COMPUTOR", variable=self.opponent_var, value="COMPUTOR", command=self.new_game).grid(row=2, column=0, sticky="w")
        ttk.Button(side, text="새 게임", command=self.new_game).grid(row=3, column=0, sticky="ew", pady=(8, 16))
        ttk.Label(side, textvariable=self.status_var, wraplength=230).grid(row=4, column=0, sticky="w")
        ttk.Label(side, textvariable=self.points_var, wraplength=230).grid(row=5, column=0, sticky="w", pady=(8, 0))
        ttk.Label(side, textvariable=self.captured_var, wraplength=230).grid(row=6, column=0, sticky="w", pady=(8, 0))
        ttk.Label(side, text="부활").grid(row=7, column=0, sticky="w", pady=(14, 0))
        for idx, piece in enumerate(("P", "N", "B", "R"), start=8):
            ttk.Button(side, text=self.revive_label(piece), command=lambda p=piece: self.on_revive(p)).grid(row=idx, column=0, sticky="ew")
        ttk.Label(
            side,
            text="잡은 말 점수: 폰 1, 나이트 3, 비숍/룩 5\n부활 비용: 폰 2, 나이트 6, 비숍/룩 10\n부활 위치: 아군 킹의 전방 1칸",
            wraplength=230,
        ).grid(row=12, column=0, sticky="w", pady=(14, 0))

    def revive_label(self, piece: str) -> str:
        names = {"P": "폰", "N": "나이트", "B": "비숍", "R": "룩"}
        return f"{names[piece]} 부활 ({REVIVE_COSTS[piece]}점)"

    def new_game(self) -> None:
        self.game = ChessGame()
        self.selected = None
        self.legal_targets = {}
        self.computer = ComputerPlayer(BLACK) if self.opponent_var.get() == "COMPUTOR" else None
        self.refresh()

    def on_square(self, row: int, col: int) -> None:
        if self.is_computer_turn():
            return
        target_move = self.legal_targets.get((row, col))
        if target_move:
            self.game.make_move(target_move)
            self.selected = None
            self.legal_targets = {}
            self.after_player_action()
            return
        piece = self.game.board[row][col]
        if piece and piece[0] == self.game.turn:
            self.selected = (row, col)
            self.legal_targets = {move.end: move for move in self.game.legal_moves() if move.start == (row, col)}
        else:
            self.selected = None
            self.legal_targets = {}
        self.refresh()

    def on_revive(self, piece: str) -> None:
        if self.is_computer_turn():
            return
        try:
            self.game.revive(piece)
        except ValueError:
            messagebox.showinfo("부활 불가", "점수, 잡힌 말, 횟수, 위치 또는 체크 상태 때문에 부활할 수 없습니다.")
            return
        self.selected = None
        self.legal_targets = {}
        self.after_player_action()

    def after_player_action(self) -> None:
        self.refresh()
        self.maybe_finish()
        if self.is_computer_turn():
            self.after(300, self.computer_turn)

    def computer_turn(self) -> None:
        if not self.computer or self.game.turn != self.computer.color:
            return
        action = self.computer.choose_action(self.game)
        if action.kind == "move" and action.move:
            self.game.make_move(action.move)
        elif action.kind == "revive" and action.revive:
            self.game.revive(action.revive.piece)
        self.refresh()
        self.maybe_finish()

    def is_computer_turn(self) -> bool:
        return self.computer is not None and self.game.turn == self.computer.color

    def maybe_finish(self) -> None:
        status = self.game.status()
        if status.startswith("Checkmate") or status == "Stalemate":
            messagebox.showinfo("게임 종료", status)

    def refresh(self) -> None:
        for r in range(8):
            for c in range(8):
                piece = self.game.board[r][c]
                button = self.buttons[r][c]
                bg = LIGHT if (r + c) % 2 == 0 else DARK
                if self.selected == (r, c):
                    bg = SELECTED
                elif (r, c) in self.legal_targets:
                    bg = LEGAL
                button.configure(text=UNICODE_PIECES.get(piece or "", ""), bg=bg, activebackground=bg)
        turn_name = "White" if self.game.turn == WHITE else "Black"
        self.status_var.set(f"Turn: {turn_name}\nStatus: {self.game.status()}\nRevive square: {self.describe_revive_square()}")
        self.points_var.set(f"Points - White: {self.game.points['w']} / Black: {self.game.points['b']}")
        self.captured_var.set(
            "Captured allies available for revive\n"
            f"White: {self.game.captured['w']}\nBlack: {self.game.captured['b']}\n"
            f"Revives used W: {self.game.revives_used['w']}\nRevives used B: {self.game.revives_used['b']}"
        )

    def describe_revive_square(self) -> str:
        square = self.game.revive_square(self.game.turn)
        return "none" if square is None else square_name(*square)


def main() -> None:
    app = ChessVariantApp()
    app.mainloop()


if __name__ == "__main__":
    main()
