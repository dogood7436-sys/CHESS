from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .ai import ComputerPlayer, DIFFICULTIES
from .game import ChessGame, Move, REVIVE_COSTS, UNICODE_PIECES, square_name

BOARD_SIZE = 640
SQUARE_SIZE = BOARD_SIZE // 8
BOARD_MARGIN = 34
CANVAS_SIZE = BOARD_SIZE + BOARD_MARGIN * 2
LIGHT = "#EED9B7"
DARK = "#A87345"
LIGHT_EDGE = "#F8EBD3"
DARK_EDGE = "#7B4B2A"
SELECTED = "#FFE66D"
LEGAL = "#69D37B"
CAPTURE = "#FF6B6B"
BACKGROUND = "#101722"
PANEL = "#182235"
PANEL_ALT = "#22314D"
TEXT = "#EEF4FF"
MUTED = "#AFC0D8"
GOLD = "#F7C948"
WHITE = "w"
BLACK = "b"


class ChessVariantApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Revive Chess")
        self.configure(bg=BACKGROUND)
        self.resizable(False, False)
        self.game = ChessGame()
        self.selected: tuple[int, int] | None = None
        self.legal_targets: dict[tuple[int, int], Move] = {}
        self.opponent_var = tk.StringVar(value="COMPUTER")
        self.difficulty_var = tk.StringVar(value="중급자")
        self.human_color = WHITE
        self.computer: ComputerPlayer | None = ComputerPlayer(BLACK, self.difficulty_var.get())
        self.status_var = tk.StringVar()
        self.points_var = tk.StringVar()
        self.captured_var = tk.StringVar()
        self._configure_style()
        self._build_layout()
        self.refresh()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("App.TFrame", background=BACKGROUND)
        style.configure("Panel.TFrame", background=PANEL, relief="flat")
        style.configure("Title.TLabel", background=PANEL, foreground=TEXT, font=("Segoe UI", 22, "bold"))
        style.configure("Subtitle.TLabel", background=PANEL, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background=PANEL, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=PANEL, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Accent.TButton", background=GOLD, foreground="#1B1B1B", font=("Segoe UI", 10, "bold"), padding=8)
        style.map("Accent.TButton", background=[("active", "#FFD966")])
        style.configure("Revive.TButton", background=PANEL_ALT, foreground=TEXT, font=("Segoe UI", 10, "bold"), padding=7)
        style.map("Revive.TButton", background=[("active", "#2F456A")])
        style.configure("TRadiobutton", background=PANEL, foreground=TEXT, font=("Segoe UI", 10))
        style.map("TRadiobutton", background=[("active", PANEL)], foreground=[("active", TEXT)])
        style.configure("TCombobox", fieldbackground="#0F1726", background=PANEL_ALT, foreground=TEXT, arrowcolor=GOLD)

    def _build_layout(self) -> None:
        root = ttk.Frame(self, padding=18, style="App.TFrame")
        root.grid(row=0, column=0)

        board_shell = tk.Frame(root, bg="#070B12", padx=10, pady=10, highlightthickness=1, highlightbackground="#31425F")
        board_shell.grid(row=0, column=0)
        self.board_canvas = tk.Canvas(
            board_shell,
            width=CANVAS_SIZE,
            height=CANVAS_SIZE,
            bg="#070B12",
            highlightthickness=0,
        )
        self.board_canvas.grid(row=0, column=0)
        self.board_canvas.bind("<Button-1>", self.on_canvas_click)

        side = ttk.Frame(root, padding=18, style="Panel.TFrame")
        side.grid(row=0, column=1, sticky="n", padx=(18, 0))
        ttk.Label(side, text="Revive Chess", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(side, text="Local tactical chess variant", style="Subtitle.TLabel").grid(row=1, column=0, sticky="w", pady=(0, 16))

        ttk.Label(side, text="상대 선택", style="Panel.TLabel").grid(row=2, column=0, sticky="w")
        ttk.Radiobutton(side, text="USER", variable=self.opponent_var, value="USER", command=self.new_game).grid(row=3, column=0, sticky="w")
        ttk.Radiobutton(side, text="COMPUTER", variable=self.opponent_var, value="COMPUTER", command=self.new_game).grid(row=4, column=0, sticky="w")
        ttk.Label(side, text="COMPUTER 난이도", style="Panel.TLabel").grid(row=5, column=0, sticky="w", pady=(10, 0))
        difficulty_box = ttk.Combobox(side, textvariable=self.difficulty_var, values=DIFFICULTIES, state="readonly", width=17)
        difficulty_box.grid(row=6, column=0, sticky="ew")
        difficulty_box.bind("<<ComboboxSelected>>", lambda _event: self.new_game())
        ttk.Button(side, text="새 게임", command=self.new_game, style="Accent.TButton").grid(row=7, column=0, sticky="ew", pady=(12, 18))

        self._separator(side, 8)
        ttk.Label(side, textvariable=self.status_var, wraplength=260, style="Panel.TLabel").grid(row=9, column=0, sticky="w", pady=(10, 0))
        ttk.Label(side, textvariable=self.points_var, wraplength=260, style="Panel.TLabel").grid(row=10, column=0, sticky="w", pady=(10, 0))
        ttk.Label(side, textvariable=self.captured_var, wraplength=260, style="Muted.TLabel").grid(row=11, column=0, sticky="w", pady=(10, 0))

        self._separator(side, 12)
        ttk.Label(side, text="부활", style="Panel.TLabel").grid(row=13, column=0, sticky="w", pady=(10, 4))
        for idx, piece in enumerate(("P", "N", "B", "R"), start=14):
            ttk.Button(side, text=self.revive_label(piece), command=lambda p=piece: self.on_revive(p), style="Revive.TButton").grid(row=idx, column=0, sticky="ew", pady=2)
        ttk.Label(
            side,
            text=(
                "잡은 말 점수: 폰 1, 나이트 3, 비숍/룩 5\n"
                "부활 비용: 폰 2, 나이트 6, 비숍/룩 10\n"
                "고급 규칙: 캐슬링, 앙파상, 50수/반복 무승부"
            ),
            wraplength=260,
            style="Muted.TLabel",
        ).grid(row=18, column=0, sticky="w", pady=(14, 0))

    def _separator(self, parent: ttk.Frame, row: int) -> None:
        tk.Frame(parent, bg="#2F405D", height=1).grid(row=row, column=0, sticky="ew", pady=4)

    def revive_label(self, piece: str) -> str:
        names = {"P": "폰", "N": "나이트", "B": "비숍", "R": "룩"}
        return f"{names[piece]} 부활  ·  {REVIVE_COSTS[piece]}점"

    def new_game(self) -> None:
        self.game = ChessGame()
        self.selected = None
        self.legal_targets = {}
        self.computer = ComputerPlayer(BLACK, self.difficulty_var.get()) if self.opponent_var.get() == "COMPUTER" else None
        self.refresh()

    def on_canvas_click(self, event: tk.Event) -> None:
        col = (event.x - BOARD_MARGIN) // SQUARE_SIZE
        row = (event.y - BOARD_MARGIN) // SQUARE_SIZE
        if 0 <= row < 8 and 0 <= col < 8:
            self.on_square(int(row), int(col))

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
        if status.startswith("Checkmate") or status == "Stalemate" or status.startswith("Draw"):
            messagebox.showinfo("게임 종료", status)

    def refresh(self) -> None:
        self.draw_board()
        turn_name = "White" if self.game.turn == WHITE else "Black"
        difficulty = self.difficulty_var.get() if self.computer else "-"
        self.status_var.set(
            f"Turn: {turn_name}\nStatus: {self.game.status()}\n"
            f"COMPUTER difficulty: {difficulty}\nRevive square: {self.describe_revive_square()}\n"
            f"Halfmove clock: {self.game.halfmove_clock}"
        )
        self.points_var.set(f"Points   White {self.game.points['w']}  ·  Black {self.game.points['b']}")
        self.captured_var.set(
            "Captured allies available for revive\n"
            f"White: {self.game.captured['w']}\nBlack: {self.game.captured['b']}\n"
            f"Revives used W: {self.game.revives_used['w']}\nRevives used B: {self.game.revives_used['b']}"
        )

    def draw_board(self) -> None:
        canvas = self.board_canvas
        canvas.delete("all")
        self.draw_board_backdrop(canvas)
        for r in range(8):
            for c in range(8):
                x1 = BOARD_MARGIN + c * SQUARE_SIZE
                y1 = BOARD_MARGIN + r * SQUARE_SIZE
                x2 = x1 + SQUARE_SIZE
                y2 = y1 + SQUARE_SIZE
                light_square = (r + c) % 2 == 0
                fill = LIGHT if light_square else DARK
                outline = LIGHT_EDGE if light_square else DARK_EDGE
                canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, width=1)
                self.draw_square_overlay(canvas, r, c, x1, y1, x2, y2)
                piece = self.game.board[r][c]
                if piece:
                    self.draw_piece(canvas, piece, x1, y1, x2, y2)
        self.draw_coordinates(canvas)
        self.draw_revive_marker(canvas)

    def draw_board_backdrop(self, canvas: tk.Canvas) -> None:
        canvas.create_rectangle(0, 0, CANVAS_SIZE, CANVAS_SIZE, fill="#070B12", outline="")
        canvas.create_rectangle(18, 18, CANVAS_SIZE - 10, CANVAS_SIZE - 10, fill="#0B1220", outline="")
        canvas.create_rectangle(
            BOARD_MARGIN - 3,
            BOARD_MARGIN - 3,
            BOARD_MARGIN + BOARD_SIZE + 3,
            BOARD_MARGIN + BOARD_SIZE + 3,
            fill="#D6A95B",
            outline="#FBE7B0",
            width=2,
        )

    def draw_square_overlay(self, canvas: tk.Canvas, r: int, c: int, x1: int, y1: int, x2: int, y2: int) -> None:
        if self.selected == (r, c):
            canvas.create_rectangle(x1 + 4, y1 + 4, x2 - 4, y2 - 4, outline=SELECTED, width=4)
        move = self.legal_targets.get((r, c))
        if move:
            target = self.game.board[r][c]
            color = CAPTURE if target or move.is_en_passant else LEGAL
            canvas.create_oval(x1 + 25, y1 + 25, x2 - 25, y2 - 25, fill=color, outline="#0D1B2A", width=2)
            if move.is_castling:
                canvas.create_text((x1 + x2) // 2, y1 + 15, text="CASTLE", fill="#0D1B2A", font=("Segoe UI", 8, "bold"))
            elif move.is_en_passant:
                canvas.create_text((x1 + x2) // 2, y1 + 15, text="E.P.", fill="#0D1B2A", font=("Segoe UI", 8, "bold"))

    def draw_piece(self, canvas: tk.Canvas, piece: str, x1: int, y1: int, x2: int, y2: int) -> None:
        glyph = UNICODE_PIECES[piece]
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2 + 2
        fill = "#F9FBFF" if piece[0] == WHITE else "#111827"
        outline = "#30415E" if piece[0] == WHITE else "#F4D58D"
        canvas.create_text(cx + 3, cy + 4, text=glyph, fill="#000000", font=("Segoe UI Symbol", 44), stipple="gray50")
        canvas.create_text(cx, cy, text=glyph, fill=outline, font=("Segoe UI Symbol", 46, "bold"))
        canvas.create_text(cx, cy - 1, text=glyph, fill=fill, font=("Segoe UI Symbol", 43, "bold"))

    def draw_coordinates(self, canvas: tk.Canvas) -> None:
        for idx, file_name in enumerate("abcdefgh"):
            x = BOARD_MARGIN + idx * SQUARE_SIZE + SQUARE_SIZE // 2
            canvas.create_text(x, BOARD_MARGIN + BOARD_SIZE + 16, text=file_name, fill=MUTED, font=("Segoe UI", 10, "bold"))
        for r in range(8):
            y = BOARD_MARGIN + r * SQUARE_SIZE + SQUARE_SIZE // 2
            canvas.create_text(BOARD_MARGIN - 16, y, text=str(8 - r), fill=MUTED, font=("Segoe UI", 10, "bold"))

    def draw_revive_marker(self, canvas: tk.Canvas) -> None:
        square = self.game.revive_square(self.game.turn)
        if square is None:
            return
        r, c = square
        x1 = BOARD_MARGIN + c * SQUARE_SIZE
        y1 = BOARD_MARGIN + r * SQUARE_SIZE
        x2 = x1 + SQUARE_SIZE
        y2 = y1 + SQUARE_SIZE
        canvas.create_rectangle(x1 + 9, y1 + 9, x2 - 9, y2 - 9, outline=GOLD, width=2, dash=(6, 4))
        canvas.create_text(x2 - 17, y1 + 16, text="✦", fill=GOLD, font=("Segoe UI Symbol", 13, "bold"))

    def describe_revive_square(self) -> str:
        square = self.game.revive_square(self.game.turn)
        return "none" if square is None else square_name(*square)


def main() -> None:
    app = ChessVariantApp()
    app.mainloop()


if __name__ == "__main__":
    main()
