(() => {
  'use strict';

  const DATA = window.REVIVE_CHESS_AI_DATA;
  const FILES = 'abcdefgh';
  const PIECES = {
    wK: '♔', wQ: '♕', wR: '♖', wB: '♗', wN: '♘', wP: '♙',
    bK: '♚', bQ: '♛', bR: '♜', bB: '♝', bN: '♞', bP: '♟'
  };
  const NAMES = { P: '폰', N: '나이트', B: '비숍', R: '룩' };
  const COSTS = DATA.reviveCosts;
  const CAPTURE_POINTS = DATA.capturePoints;

  const clone = (value) => JSON.parse(JSON.stringify(value));
  const opposite = (color) => color === 'w' ? 'b' : 'w';
  const inBounds = (r, c) => r >= 0 && r < 8 && c >= 0 && c < 8;
  const squareName = (r, c) => `${FILES[c]}${8 - r}`;
  const homeKingSquare = (color) => color === 'w' ? [7, 4] : [0, 4];
  const homeRookSquare = (color, side) => [color === 'w' ? 7 : 0, side === 'K' ? 7 : 0];

  class Move {
    constructor(start, end, { promotion = null, isCastling = false, isEnPassant = false } = {}) {
      this.start = start;
      this.end = end;
      this.promotion = promotion;
      this.isCastling = isCastling;
      this.isEnPassant = isEnPassant;
    }
    uci() {
      return `${squareName(...this.start)}${squareName(...this.end)}${(this.promotion || '').toLowerCase()}`;
    }
  }

  class ChessGame {
    constructor() {
      this.board = [
        ['bR', 'bN', 'bB', 'bQ', 'bK', 'bB', 'bN', 'bR'],
        Array(8).fill('bP'),
        Array(8).fill(null), Array(8).fill(null), Array(8).fill(null), Array(8).fill(null),
        Array(8).fill('wP'),
        ['wR', 'wN', 'wB', 'wQ', 'wK', 'wB', 'wN', 'wR']
      ];
      this.turn = 'w';
      this.points = { w: 0, b: 0 };
      this.captured = { w: [], b: [] };
      this.revivesUsed = { w: { P: 0, N: 0, BR: 0 }, b: { P: 0, N: 0, BR: 0 } };
      this.castlingRights = { w: { K: true, Q: true }, b: { K: true, Q: true } };
      this.enPassantTarget = null;
      this.halfmoveClock = 0;
      this.fullmoveNumber = 1;
      this.moveLog = [];
      this.positionCounts = {};
      this.positionCounts[this.positionKey()] = 1;
    }

    copy() {
      const game = Object.create(ChessGame.prototype);
      game.board = clone(this.board);
      game.turn = this.turn;
      game.points = clone(this.points);
      game.captured = clone(this.captured);
      game.revivesUsed = clone(this.revivesUsed);
      game.castlingRights = clone(this.castlingRights);
      game.enPassantTarget = this.enPassantTarget ? [...this.enPassantTarget] : null;
      game.halfmoveClock = this.halfmoveClock;
      game.fullmoveNumber = this.fullmoveNumber;
      game.moveLog = [...this.moveLog];
      game.positionCounts = clone(this.positionCounts);
      return game;
    }

    legalMoves(color = this.turn) {
      const moves = [];
      for (let r = 0; r < 8; r += 1) {
        for (let c = 0; c < 8; c += 1) {
          const piece = this.board[r][c];
          if (!piece || piece[0] !== color) continue;
          for (const move of this.pseudoMoves(r, c)) {
            const trial = this.copy();
            trial.applyMoveNoValidation(move);
            if (!trial.inCheck(color)) moves.push(move);
          }
        }
      }
      return moves;
    }

    legalRevives(color = this.turn) {
      if (this.inCheck(color)) return [];
      const square = this.reviveSquare(color);
      if (!square || this.board[square[0]][square[1]]) return [];
      const actions = [];
      for (const piece of ['P', 'N', 'B', 'R']) {
        if (!this.canRevive(color, piece)) continue;
        const trial = this.copy();
        trial.applyReviveNoValidation(piece, color);
        if (!trial.inCheck(color)) actions.push({ color, piece, square });
      }
      return actions;
    }

    canRevive(color, piece) {
      if (!Object.hasOwn(COSTS, piece) || !this.captured[color].includes(piece)) return false;
      if (this.points[color] < COSTS[piece]) return false;
      if (piece === 'P') return this.revivesUsed[color].P < 2;
      if (piece === 'N') return this.revivesUsed[color].N < 1;
      if (piece === 'B' || piece === 'R') return this.revivesUsed[color].BR < 1;
      return false;
    }

    makeMove(move) {
      const legal = new Map(this.legalMoves(this.turn).map((candidate) => [candidate.uci(), candidate]));
      if (!legal.has(move.uci())) throw new Error('Illegal move');
      this.applyMoveNoValidation(legal.get(move.uci()));
      this.turn = opposite(this.turn);
      this.finishTurn();
    }

    revive(piece) {
      const action = this.legalRevives(this.turn).find((candidate) => candidate.piece === piece);
      if (!action) throw new Error('Illegal revive');
      this.applyReviveNoValidation(piece, this.turn);
      this.turn = opposite(this.turn);
      this.finishTurn();
      return action;
    }

    status() {
      if (this.halfmoveClock >= 100) return 'Draw: 50-move rule';
      if ((this.positionCounts[this.positionKey()] || 0) >= 3) return 'Draw: threefold repetition';
      if (this.inCheck(this.turn)) {
        if (!this.legalMoves(this.turn).length && !this.legalRevives(this.turn).length) {
          return `Checkmate: ${opposite(this.turn) === 'w' ? 'White' : 'Black'} wins`;
        }
        return 'Check';
      }
      if (!this.legalMoves(this.turn).length && !this.legalRevives(this.turn).length) return 'Stalemate';
      return 'Playing';
    }

    reviveSquare(color) {
      const king = this.kingSquare(color);
      if (!king) return null;
      const row = king[0] + (color === 'w' ? -1 : 1);
      return inBounds(row, king[1]) ? [row, king[1]] : null;
    }

    kingSquare(color) {
      const target = `${color}K`;
      for (let r = 0; r < 8; r += 1) for (let c = 0; c < 8; c += 1) if (this.board[r][c] === target) return [r, c];
      return null;
    }

    inCheck(color) {
      const king = this.kingSquare(color);
      return !king || this.squareAttacked(king[0], king[1], opposite(color));
    }

    squareAttacked(row, col, byColor) {
      for (let r = 0; r < 8; r += 1) {
        for (let c = 0; c < 8; c += 1) {
          const piece = this.board[r][c];
          if (!piece || piece[0] !== byColor) continue;
          if (this.attacksFrom(r, c).some(([ar, ac]) => ar === row && ac === col)) return true;
        }
      }
      return false;
    }

    positionKey() {
      const board = this.board.map((row) => row.map((piece) => piece || '--').join('')).join('/');
      const rights = ['wK', 'wQ', 'bK', 'bQ'].filter((right) => this.castlingRights[right[0]][right[1]]).join('') || '-';
      const ep = this.enPassantTarget ? squareName(...this.enPassantTarget) : '-';
      const variant = `wp${this.points.w}bp${this.points.b}|wc${[...this.captured.w].sort().join('')}|bc${[...this.captured.b].sort().join('')}|wr${JSON.stringify(this.revivesUsed.w)}|br${JSON.stringify(this.revivesUsed.b)}`;
      return `${board} ${this.turn} ${rights} ${ep} ${variant}`;
    }

    finishTurn() {
      if (this.turn === 'w') this.fullmoveNumber += 1;
      const key = this.positionKey();
      this.positionCounts[key] = (this.positionCounts[key] || 0) + 1;
    }

    applyMoveNoValidation(move) {
      const [sr, sc] = move.start;
      const [er, ec] = move.end;
      const piece = this.board[sr][sc];
      if (!piece) throw new Error('No piece');
      const capturedSquare = move.isEnPassant ? [sr, ec] : [er, ec];
      const capturedPiece = this.board[capturedSquare[0]][capturedSquare[1]];
      this.board[sr][sc] = null;
      if (move.isEnPassant) this.board[capturedSquare[0]][capturedSquare[1]] = null;
      this.board[er][ec] = piece[1] === 'P' && (er === 0 || er === 7) ? `${piece[0]}${move.promotion || 'Q'}` : piece;
      if (move.isCastling) {
        const rookStart = ec === 6 ? 7 : 0;
        const rookEnd = ec === 6 ? 5 : 3;
        this.board[sr][rookEnd] = this.board[sr][rookStart];
        this.board[sr][rookStart] = null;
      }
      this.updateCastlingRights(piece, move.start, capturedPiece, capturedSquare);
      this.enPassantTarget = null;
      if (piece[1] === 'P' && Math.abs(er - sr) === 2) this.enPassantTarget = [(sr + er) / 2, sc];
      if (capturedPiece) {
        this.points[piece[0]] += CAPTURE_POINTS[capturedPiece[1]] || 0;
        this.captured[capturedPiece[0]].push(capturedPiece[1]);
        this.moveLog.push(`${piece}@${squareName(sr, sc)}x${capturedPiece}@${squareName(...capturedSquare)}`);
      } else {
        this.moveLog.push(`${piece}@${squareName(sr, sc)}-${squareName(er, ec)}`);
      }
      this.halfmoveClock = piece[1] === 'P' || capturedPiece ? 0 : this.halfmoveClock + 1;
    }

    updateCastlingRights(piece, start, capturedPiece, capturedSquare) {
      const color = piece[0];
      if (piece[1] === 'K') this.castlingRights[color] = { K: false, Q: false };
      if (piece[1] === 'R') {
        for (const side of ['K', 'Q']) {
          const [rr, rc] = homeRookSquare(color, side);
          if (start[0] === rr && start[1] === rc) this.castlingRights[color][side] = false;
        }
      }
      if (capturedPiece?.[1] === 'R') {
        for (const side of ['K', 'Q']) {
          const [rr, rc] = homeRookSquare(capturedPiece[0], side);
          if (capturedSquare[0] === rr && capturedSquare[1] === rc) this.castlingRights[capturedPiece[0]][side] = false;
        }
      }
    }

    applyReviveNoValidation(piece, color) {
      const [r, c] = this.reviveSquare(color);
      this.board[r][c] = `${color}${piece}`;
      this.points[color] -= COSTS[piece];
      this.captured[color].splice(this.captured[color].indexOf(piece), 1);
      if (piece === 'P') this.revivesUsed[color].P += 1;
      else if (piece === 'N') this.revivesUsed[color].N += 1;
      else this.revivesUsed[color].BR += 1;
      this.enPassantTarget = null;
      this.halfmoveClock += 1;
      this.moveLog.push(`${color}${piece} revived@${squareName(r, c)}`);
    }

    pseudoMoves(r, c) {
      const piece = this.board[r][c];
      if (!piece) return [];
      const [color, kind] = piece;
      const enemy = opposite(color);
      const moves = [];
      if (kind === 'P') {
        const direction = color === 'w' ? -1 : 1;
        const startRow = color === 'w' ? 6 : 1;
        const nr = r + direction;
        if (inBounds(nr, c) && !this.board[nr][c]) {
          moves.push(new Move([r, c], [nr, c], { promotion: (nr === 0 || nr === 7) ? 'Q' : null }));
          const nnr = r + 2 * direction;
          if (r === startRow && inBounds(nnr, c) && !this.board[nnr][c]) moves.push(new Move([r, c], [nnr, c]));
        }
        for (const dc of [-1, 1]) {
          const nc = c + dc;
          if (inBounds(nr, nc) && this.board[nr][nc]?.[0] === enemy && this.board[nr][nc][1] !== 'K') {
            moves.push(new Move([r, c], [nr, nc], { promotion: (nr === 0 || nr === 7) ? 'Q' : null }));
          }
          if (this.enPassantTarget?.[0] === nr && this.enPassantTarget?.[1] === nc && this.board[r][nc] === `${enemy}P`) {
            moves.push(new Move([r, c], [nr, nc], { isEnPassant: true }));
          }
        }
      } else if (kind === 'N') {
        for (const [dr, dc] of [[-2,-1],[-2,1],[-1,-2],[-1,2],[1,-2],[1,2],[2,-1],[2,1]]) this.addIfValid(moves, color, r, c, r + dr, c + dc);
      } else if (['B', 'R', 'Q'].includes(kind)) {
        const dirs = [];
        if (kind === 'B' || kind === 'Q') dirs.push([-1,-1],[-1,1],[1,-1],[1,1]);
        if (kind === 'R' || kind === 'Q') dirs.push([-1,0],[1,0],[0,-1],[0,1]);
        for (const [dr, dc] of dirs) {
          let nr2 = r + dr, nc2 = c + dc;
          while (inBounds(nr2, nc2)) {
            const target = this.board[nr2][nc2];
            if (!target) moves.push(new Move([r, c], [nr2, nc2]));
            else {
              if (target[0] !== color && target[1] !== 'K') moves.push(new Move([r, c], [nr2, nc2]));
              break;
            }
            nr2 += dr; nc2 += dc;
          }
        }
      } else if (kind === 'K') {
        for (const dr of [-1, 0, 1]) for (const dc of [-1, 0, 1]) if (dr || dc) this.addIfValid(moves, color, r, c, r + dr, c + dc);
        moves.push(...this.castlingMoves(color, r, c));
      }
      return moves;
    }

    addIfValid(moves, color, sr, sc, er, ec) {
      if (!inBounds(er, ec)) return;
      const target = this.board[er][ec];
      if (!target || (target[0] !== color && target[1] !== 'K')) moves.push(new Move([sr, sc], [er, ec]));
    }

    castlingMoves(color, r, c) {
      const [kr, kc] = homeKingSquare(color);
      if (this.inCheck(color) || r !== kr || c !== kc) return [];
      const moves = [];
      for (const [side, endCol, between, safe] of [['K', 6, [5, 6], [5, 6]], ['Q', 2, [1, 2, 3], [3, 2]]]) {
        if (!this.castlingRights[color][side]) continue;
        const [rr, rc] = homeRookSquare(color, side);
        if (this.board[rr][rc] !== `${color}R`) continue;
        if (between.some((col) => this.board[r][col])) continue;
        if (safe.some((col) => this.squareAttacked(r, col, opposite(color)))) continue;
        moves.push(new Move([r, c], [r, endCol], { isCastling: true }));
      }
      return moves;
    }

    attacksFrom(r, c) {
      const piece = this.board[r][c];
      if (!piece) return [];
      const [color, kind] = piece;
      const attacks = [];
      if (kind === 'P') {
        const direction = color === 'w' ? -1 : 1;
        for (const dc of [-1, 1]) if (inBounds(r + direction, c + dc)) attacks.push([r + direction, c + dc]);
      } else if (kind === 'N') {
        for (const [dr, dc] of [[-2,-1],[-2,1],[-1,-2],[-1,2],[1,-2],[1,2],[2,-1],[2,1]]) if (inBounds(r + dr, c + dc)) attacks.push([r + dr, c + dc]);
      } else if (['B', 'R', 'Q'].includes(kind)) {
        const dirs = [];
        if (kind === 'B' || kind === 'Q') dirs.push([-1,-1],[-1,1],[1,-1],[1,1]);
        if (kind === 'R' || kind === 'Q') dirs.push([-1,0],[1,0],[0,-1],[0,1]);
        for (const [dr, dc] of dirs) {
          let nr = r + dr, nc = c + dc;
          while (inBounds(nr, nc)) {
            attacks.push([nr, nc]);
            if (this.board[nr][nc]) break;
            nr += dr; nc += dc;
          }
        }
      } else if (kind === 'K') {
        for (const dr of [-1, 0, 1]) for (const dc of [-1, 0, 1]) if ((dr || dc) && inBounds(r + dr, c + dc)) attacks.push([r + dr, c + dc]);
      }
      return attacks;
    }
  }

  class ComputerPlayer {
    constructor(color, difficulty = '중급자') {
      this.color = color;
      this.difficulty = ['초급자', '중급자', '상급자'].includes(difficulty) ? difficulty : '중급자';
    }
    chooseAction(game) {
      const actions = this.actionsFor(game, this.color);
      if (!actions.length) return { kind: 'none', score: -999999 };
      if (this.difficulty === '초급자') return actions[Math.floor(Math.random() * actions.length)];
      if (this.difficulty === '상급자') return this.chooseAdvanced(game, actions);
      return this.chooseIntermediate(game, actions);
    }
    actionsFor(game, color) {
      return [
        ...game.legalMoves(color).map((move) => ({ kind: 'move', move })),
        ...game.legalRevives(color).map((revive) => ({ kind: 'revive', revive }))
      ];
    }
    chooseIntermediate(game, actions) {
      const scored = actions.map((action) => ({ ...action, score: this.scoreAction(game, action) + Math.floor(Math.random() * 31) - 15 }));
      const best = Math.max(...scored.map((action) => action.score));
      const topBand = scored.filter((action) => action.score >= best - 30);
      return topBand[Math.floor(Math.random() * topBand.length)];
    }
    chooseAdvanced(game, actions) {
      const scored = actions.map((action) => {
        const trial = this.applyAction(game, action);
        return { ...action, score: this.minimax(trial, 2, trial.turn === this.color, -999999, 999999) + this.specialBonus(action) };
      });
      const best = Math.max(...scored.map((action) => action.score));
      return scored.find((action) => action.score === best);
    }
    minimax(game, depth, maximizing, alpha, beta) {
      const status = game.status();
      if (depth === 0 || !['Playing', 'Check'].includes(status)) return this.terminalScore(game, status);
      const actions = this.actionsFor(game, game.turn);
      if (!actions.length) return this.terminalScore(game, status);
      if (maximizing) {
        let value = -999999;
        for (const action of actions) {
          value = Math.max(value, this.minimax(this.applyAction(game, action), depth - 1, false, alpha, beta));
          alpha = Math.max(alpha, value);
          if (beta <= alpha) break;
        }
        return value;
      }
      let value = 999999;
      for (const action of actions) {
        value = Math.min(value, this.minimax(this.applyAction(game, action), depth - 1, true, alpha, beta));
        beta = Math.min(beta, value);
        if (beta <= alpha) break;
      }
      return value;
    }
    terminalScore(game, status) {
      if (status.startsWith('Checkmate')) return opposite(game.turn) === this.color ? 999999 : -999999;
      if (status.startsWith('Draw') || status === 'Stalemate') return 0;
      return this.evaluate(game);
    }
    scoreAction(game, action) {
      const trial = this.applyAction(game, action);
      let score = this.evaluate(trial) + this.specialBonus(action);
      if (action.move && DATA.openingMoves.includes(action.move.uci().slice(0, 4)) && game.moveLog.length < 8) score += 25;
      return score;
    }
    applyAction(game, action) {
      const trial = game.copy();
      if (action.kind === 'move') trial.makeMove(action.move);
      if (action.kind === 'revive') trial.revive(action.revive.piece);
      return trial;
    }
    specialBonus(action) {
      if (action.kind === 'revive') return { P: 60, N: 130, B: 150, R: 170 }[action.revive.piece] || 0;
      if (action.move?.isCastling) return 90;
      if (action.move?.isEnPassant) return 45;
      return 0;
    }
    evaluate(game) {
      let score = 0;
      for (let r = 0; r < 8; r += 1) {
        for (let c = 0; c < 8; c += 1) {
          const piece = game.board[r][c];
          if (!piece) continue;
          const [color, kind] = piece;
          const table = DATA.pieceSquare[kind] || Array(64).fill(0);
          const index = color === 'w' ? r * 8 + c : (7 - r) * 8 + c;
          const value = DATA.material[kind] + table[index];
          score += color === this.color ? value : -value;
        }
      }
      score += (game.points[this.color] - game.points[opposite(this.color)]) * 35;
      if (game.inCheck(opposite(this.color))) score += 40;
      if (game.inCheck(this.color)) score -= 80;
      return score;
    }
  }

  class ReviveChessUi {
    constructor() {
      this.game = new ChessGame();
      this.selected = null;
      this.legalTargets = new Map();
      this.computer = new ComputerPlayer('b', this.difficultyValue());
      this.boardEl = document.querySelector('#board');
      this.statusEl = document.querySelector('#statusText');
      this.capturedEl = document.querySelector('#capturedText');
      this.turnBadge = document.querySelector('#turnBadge');
      this.reviveButtons = new Map([...document.querySelectorAll('[data-revive]')].map((button) => [button.dataset.revive, button]));
      this.bindEvents();
      this.render();
    }
    bindEvents() {
      document.querySelector('#newGame').addEventListener('click', () => this.newGame());
      document.querySelector('#difficulty').addEventListener('change', () => this.newGame());
      document.querySelectorAll('input[name="opponent"]').forEach((input) => input.addEventListener('change', () => this.newGame()));
      document.querySelectorAll('[data-revive]').forEach((button) => button.addEventListener('click', () => this.onRevive(button.dataset.revive)));
    }
    opponentValue() { return document.querySelector('input[name="opponent"]:checked').value; }
    difficultyValue() { return document.querySelector('#difficulty').value; }
    newGame() {
      this.game = new ChessGame();
      this.selected = null;
      this.legalTargets = new Map();
      this.computer = this.opponentValue() === 'COMPUTER' ? new ComputerPlayer('b', this.difficultyValue()) : null;
      this.render();
    }
    onSquare(row, col) {
      if (this.isComputerTurn()) return;
      const key = `${row},${col}`;
      if (this.legalTargets.has(key)) {
        this.game.makeMove(this.legalTargets.get(key));
        this.selected = null;
        this.legalTargets.clear();
        this.afterPlayerAction();
        return;
      }
      const piece = this.game.board[row][col];
      if (piece?.[0] === this.game.turn) {
        this.selected = [row, col];
        this.legalTargets = new Map(this.game.legalMoves().filter((move) => move.start[0] === row && move.start[1] === col).map((move) => [`${move.end[0]},${move.end[1]}`, move]));
      } else {
        this.selected = null;
        this.legalTargets.clear();
      }
      this.render();
    }
    onRevive(piece) {
      if (this.isComputerTurn()) return;
      try {
        this.game.revive(piece);
        this.selected = null;
        this.legalTargets.clear();
        this.afterPlayerAction();
      } catch (_error) {
        alert('점수, 잡힌 말, 횟수, 위치 또는 체크 상태 때문에 부활할 수 없습니다.');
      }
    }
    afterPlayerAction() {
      this.render();
      this.maybeFinish();
      if (this.isComputerTurn()) window.setTimeout(() => this.computerTurn(), 250);
    }
    computerTurn() {
      if (!this.isComputerTurn()) return;
      const action = this.computer.chooseAction(this.game);
      if (action.kind === 'move') this.game.makeMove(action.move);
      if (action.kind === 'revive') this.game.revive(action.revive.piece);
      this.render();
      this.maybeFinish();
    }
    isComputerTurn() { return this.computer && this.game.turn === this.computer.color; }
    maybeFinish() {
      const status = this.game.status();
      if (status.startsWith('Checkmate') || status.startsWith('Draw') || status === 'Stalemate') alert(`게임 종료: ${status}`);
    }
    render() {
      this.renderBoard();
      const turn = this.game.turn === 'w' ? 'White' : 'Black';
      this.turnBadge.textContent = turn;
      document.querySelector('#whiteScore').textContent = this.game.points.w;
      document.querySelector('#blackScore').textContent = this.game.points.b;
      this.statusEl.textContent = `Turn: ${turn}\nStatus: ${this.game.status()}\nCOMPUTER difficulty: ${this.computer ? this.difficultyValue() : '-'}\nRevive square: ${this.describeReviveSquare()}\nHalfmove clock: ${this.game.halfmoveClock}`;
      this.capturedEl.textContent = `Captured allies available for revive\nWhite: ${JSON.stringify(this.game.captured.w)}\nBlack: ${JSON.stringify(this.game.captured.b)}\nRevive counters W: ${this.reviveCounterText('w')}\nRevive counters B: ${this.reviveCounterText('b')}`;
      this.updateReviveButtons();
    }
    reviveRemaining(color, piece) {
      if (piece === 'P') return Math.max(0, 2 - this.game.revivesUsed[color].P);
      if (piece === 'N') return Math.max(0, 1 - this.game.revivesUsed[color].N);
      return Math.max(0, 1 - this.game.revivesUsed[color].BR);
    }
    reviveCounterText(color) {
      return `P ${this.reviveRemaining(color, 'P')}/2, N ${this.reviveRemaining(color, 'N')}/1, B/R ${this.reviveRemaining(color, 'B')}/1`;
    }
    updateReviveButtons() {
      const legalPieces = new Set(this.game.legalRevives(this.game.turn).map((action) => action.piece));
      const inCheck = this.game.inCheck(this.game.turn);
      for (const [piece, button] of this.reviveButtons.entries()) {
        const remaining = this.reviveRemaining(this.game.turn, piece);
        const exhausted = remaining === 0;
        button.textContent = `${NAMES[piece]} · ${COSTS[piece]}점 · 남은 ${remaining}회`;
        button.classList.toggle('spent', exhausted);
        button.disabled = exhausted || inCheck || !legalPieces.has(piece) || this.isComputerTurn();
        button.title = inCheck ? '체크 상태에서는 부활할 수 없습니다.' : exhausted ? '부활 카운터를 모두 사용했습니다.' : '';
      }
    }
    renderBoard() {
      this.boardEl.innerHTML = '';
      const revive = this.game.reviveSquare(this.game.turn);
      for (let r = 0; r < 8; r += 1) {
        for (let c = 0; c < 8; c += 1) {
          const square = document.createElement('button');
          square.type = 'button';
          square.className = `square ${(r + c) % 2 === 0 ? 'light' : 'dark'}`;
          if (this.selected?.[0] === r && this.selected?.[1] === c) square.classList.add('selected');
          if (revive?.[0] === r && revive?.[1] === c) square.classList.add('revive-square');
          const move = this.legalTargets.get(`${r},${c}`);
          if (move) square.classList.add((this.game.board[r][c] || move.isEnPassant) ? 'capture' : 'legal');
          square.addEventListener('click', () => this.onSquare(r, c));
          if (r === 7) square.append(this.coord(FILES[c]));
          if (move?.isCastling || move?.isEnPassant) square.append(this.tag(move.isCastling ? 'CASTLE' : 'E.P.'));
          const piece = this.game.board[r][c];
          if (piece) {
            const span = document.createElement('span');
            span.className = `piece ${piece[0] === 'w' ? 'white' : 'black'}`;
            span.textContent = PIECES[piece];
            square.append(span);
          }
          this.boardEl.append(square);
        }
      }
    }
    coord(text) { const el = document.createElement('span'); el.className = 'coord'; el.textContent = text; return el; }
    tag(text) { const el = document.createElement('span'); el.className = 'tag'; el.textContent = text; return el; }
    describeReviveSquare() {
      const square = this.game.reviveSquare(this.game.turn);
      return square ? squareName(...square) : 'none';
    }
  }

  window.ReviveChess = { ChessGame, ComputerPlayer, Move };
  window.addEventListener('DOMContentLoaded', () => new ReviveChessUi());
})();
