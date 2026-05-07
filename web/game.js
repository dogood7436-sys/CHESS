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
  const REVIVE_COUNTER_LIMIT = DATA.reviveCounterLimit;
  const CAPTURE_POINTS = DATA.capturePoints;
  const SKILL_CARDS = [
    { id: 'valiant_warrior', name: '용맹한 전사', type: '액티브', uses: '1회 사용 가능', description: '폰이 정면의 상대 말을 잡을 수 있습니다.' },
    { id: 'wedge_charge', name: '쐐기 돌진', type: '액티브', uses: '1회 사용 가능', description: '나이트가 직선 방향 2칸 안에 있는 말을 잡을 수 있습니다.' },
    { id: 'brilliant_scheme', name: '비상한 계책', type: '패시브', description: '자신의 부활 카운터가 1개 증가합니다.' },
    { id: 'wicked_scheme', name: '사악한 술수', type: '패시브', description: '상대의 부활 카운터가 1개 감소합니다.' },
    { id: 'iron_empress', name: '철혈의 여제', type: '액티브', uses: '1회 사용 가능', description: '퀸이 죽은 턴에 아군 나이트 하나를 지우고 퀸을 킹 앞에서 부활시킵니다.' },
    { id: 'knight_king', name: '기사왕', type: '액티브', uses: '1회 사용 가능', description: '킹이 직선 거리의 말을 잡을 수 있습니다. 상대 킹에게는 사용할 수 없습니다.' },
    { id: 'trickster', name: '트릭스터', type: '액티브', uses: '3턴마다 사용 가능', description: '비숍이 직선 거리 한 칸을 이동할 수 있습니다.' },
    { id: 'destroyer_chariot', name: '파괴전차', type: '패시브', description: '룩이 적 말을 잡으면 다음 자신의 턴까지 상대 룩과 비숍은 자신의 룩을 잡을 수 없습니다.' }
  ];
  const clone = (value) => JSON.parse(JSON.stringify(value));
  const opposite = (color) => color === 'w' ? 'b' : 'w';
  const inBounds = (r, c) => r >= 0 && r < 8 && c >= 0 && c < 8;
  const squareName = (r, c) => `${FILES[c]}${8 - r}`;
  const cardKind = (card) => card?.type || '액티브';
  const isPassiveCard = (card) => cardKind(card) === '패시브';
  const randomCardId = () => SKILL_CARDS[Math.floor(Math.random() * SKILL_CARDS.length)].id;
  const randomCards = () => ({ w: randomCardId(), b: randomCardId() });
  const MOVE_SKILL_CARDS = new Set(['valiant_warrior', 'wedge_charge', 'knight_king', 'trickster']);
  const homeKingSquare = (color) => color === 'w' ? [7, 4] : [0, 4];
  const homeRookSquare = (color, side) => [color === 'w' ? 7 : 0, side === 'K' ? 7 : 0];

  class Move {
    constructor(start, end, { promotion = null, isCastling = false, isEnPassant = false, skillCard = null } = {}) {
      this.start = start;
      this.end = end;
      this.promotion = promotion;
      this.isCastling = isCastling;
      this.isEnPassant = isEnPassant;
      this.skillCard = skillCard;
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
      this.revivesUsed = { w: 0, b: 0 };
      this.selectedCards = randomCards();
      this.usedCards = { w: false, b: false };
      this.activeCardArmed = { w: null, b: null };
      this.reviveLimitBonus = { w: 0, b: 0 };
      this.tricksterCooldown = { w: 0, b: 0 };
      this.rookProtection = { w: 0, b: 0 };
      this.queenReviveWindow = { w: false, b: false };
      this.applyAssignedPassiveCards();
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
      game.selectedCards = clone(this.selectedCards);
      game.usedCards = clone(this.usedCards);
      game.activeCardArmed = clone(this.activeCardArmed);
      game.reviveLimitBonus = clone(this.reviveLimitBonus);
      game.tricksterCooldown = clone(this.tricksterCooldown);
      game.rookProtection = clone(this.rookProtection);
      game.queenReviveWindow = clone(this.queenReviveWindow);
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
      return this.revivesUsed[color] + COSTS[piece] <= this.effectiveReviveLimit(color);
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
      const variant = `wp${this.points.w}bp${this.points.b}|wc${[...this.captured.w].sort().join('')}|bc${[...this.captured.b].sort().join('')}|wr${JSON.stringify(this.revivesUsed.w)}|br${JSON.stringify(this.revivesUsed.b)}|rl${JSON.stringify(this.reviveLimitBonus)}`;
      return `${board} ${this.turn} ${rights} ${ep} ${variant}`;
    }

    finishTurn() {
      const previous = opposite(this.turn);
      this.activeCardArmed[previous] = null;
      this.queenReviveWindow[previous] = false;
      if (this.tricksterCooldown[this.turn] > 0) this.tricksterCooldown[this.turn] -= 1;
      if (this.rookProtection[this.turn] > 0) this.rookProtection[this.turn] -= 1;
      if (this.turn === 'w') this.fullmoveNumber += 1;
      const key = this.positionKey();
      this.positionCounts[key] = (this.positionCounts[key] || 0) + 1;
    }

    effectiveReviveLimit(color) {
      return Math.max(0, REVIVE_COUNTER_LIMIT + this.reviveLimitBonus[color]);
    }

    resetSkillState() {
      this.usedCards = { w: false, b: false };
      this.activeCardArmed = { w: null, b: null };
      this.reviveLimitBonus = { w: 0, b: 0 };
      this.tricksterCooldown = { w: 0, b: 0 };
      this.rookProtection = { w: 0, b: 0 };
      this.queenReviveWindow = { w: false, b: false };
      this.applyAssignedPassiveCards();
    }

    applyAssignedPassiveCards() {
      for (const color of ['w', 'b']) {
        const card = this.selectedCard(color);
        if (card?.id === 'brilliant_scheme') {
          this.reviveLimitBonus[color] += 1;
          this.usedCards[color] = true;
        }
        if (card?.id === 'wicked_scheme') {
          this.reviveLimitBonus[opposite(color)] -= 1;
          this.usedCards[color] = true;
        }
      }
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
      if (move.skillCard) this.consumeSkillCard(piece[0], move.skillCard);
      this.updateCastlingRights(piece, move.start, capturedPiece, capturedSquare);
      this.enPassantTarget = null;
      if (piece[1] === 'P' && Math.abs(er - sr) === 2) this.enPassantTarget = [(sr + er) / 2, sc];
      if (capturedPiece) {
        this.points[piece[0]] += CAPTURE_POINTS[capturedPiece[1]] || 0;
        this.captured[capturedPiece[0]].push(capturedPiece[1]);
        if (capturedPiece[1] === 'Q') this.queenReviveWindow[capturedPiece[0]] = true;
        if (piece[1] === 'R' && this.selectedCards[piece[0]] === 'destroyer_chariot') this.rookProtection[piece[0]] = 1;
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
      this.captured[color].splice(this.captured[color].indexOf(piece), 1);
      this.revivesUsed[color] += COSTS[piece];
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
        if (this.cardReady(color, 'valiant_warrior') && inBounds(nr, c) && this.board[nr][c]?.[0] === enemy && this.board[nr][c][1] !== 'K') {
          moves.push(new Move([r, c], [nr, c], { promotion: (nr === 0 || nr === 7) ? 'Q' : null, skillCard: 'valiant_warrior' }));
        }
      } else if (kind === 'N') {
        for (const [dr, dc] of [[-2,-1],[-2,1],[-1,-2],[-1,2],[1,-2],[1,2],[2,-1],[2,1]]) this.addIfValid(moves, color, kind, r, c, r + dr, c + dc);
        if (this.cardReady(color, 'wedge_charge')) {
          for (const [dr, dc] of [[-1,0],[1,0],[0,-1],[0,1]]) {
            for (const distance of [1, 2]) {
              const tr = r + dr * distance, tc = c + dc * distance;
              if (!inBounds(tr, tc)) break;
              const target = this.board[tr][tc];
              if (!target) continue;
              if (target[0] === enemy && target[1] !== 'K') moves.push(new Move([r, c], [tr, tc], { skillCard: 'wedge_charge' }));
              break;
            }
          }
        }
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
              if (target[0] !== color && target[1] !== 'K' && !this.protectedRookCaptureBlocked(kind, target)) moves.push(new Move([r, c], [nr2, nc2]));
              break;
            }
            nr2 += dr; nc2 += dc;
          }
        }
        if (kind === 'B' && this.cardReady(color, 'trickster')) {
          for (const [dr, dc] of [[-1,0],[1,0],[0,-1],[0,1]]) this.addIfValid(moves, color, kind, r, c, r + dr, c + dc, 'trickster');
        }
      } else if (kind === 'K') {
        for (const dr of [-1, 0, 1]) for (const dc of [-1, 0, 1]) if (dr || dc) this.addIfValid(moves, color, kind, r, c, r + dr, c + dc);
        if (this.cardReady(color, 'knight_king')) {
          for (const [dr, dc] of [[-1,0],[1,0],[0,-1],[0,1]]) {
            let tr = r + dr, tc = c + dc;
            while (inBounds(tr, tc)) {
              const target = this.board[tr][tc];
              if (target) {
                if (target[0] === enemy && target[1] !== 'K') moves.push(new Move([r, c], [tr, tc], { skillCard: 'knight_king' }));
                break;
              }
              tr += dr; tc += dc;
            }
          }
        }
        moves.push(...this.castlingMoves(color, r, c));
      }
      return moves;
    }

    protectedRookCaptureBlocked(attackerKind, target) {
      return ['B', 'R'].includes(attackerKind) && target?.[1] === 'R' && this.rookProtection[target[0]] > 0;
    }

    addIfValid(moves, color, attackerKind, sr, sc, er, ec, skillCard = null) {
      if (!inBounds(er, ec)) return;
      const target = this.board[er][ec];
      if (!target || (target[0] !== color && target[1] !== 'K' && !this.protectedRookCaptureBlocked(attackerKind, target))) {
        moves.push(new Move([sr, sc], [er, ec], { skillCard }));
      }
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

    hasUnusedCard(color, id = null) {
      return !this.usedCards[color] && (!id || this.selectedCards[color] === id);
    }

    cardReady(color, id) {
      if (this.selectedCards[color] !== id) return false;
      if (id === 'trickster') return this.activeCardArmed[color] === id && this.tricksterCooldown[color] === 0;
      return this.activeCardArmed[color] === id && !this.usedCards[color];
    }

    consumeCard(color) {
      this.usedCards[color] = true;
      this.activeCardArmed[color] = null;
    }

    consumeSkillCard(color, id) {
      this.activeCardArmed[color] = null;
      if (id === 'trickster') {
        this.tricksterCooldown[color] = 3;
        return;
      }
      this.usedCards[color] = true;
    }

    selectedCard(color) {
      return SKILL_CARDS.find((card) => card.id === this.selectedCards[color]);
    }

    activateCard(color) {
      const card = this.selectedCard(color);
      if (!card) return { ok: false, message: '기술 카드가 없습니다.' };
      if (isPassiveCard(card)) return { ok: false, message: '패시브 카드는 조건에 따라 자동 적용됩니다.' };
      if (card.id === 'trickster' && this.tricksterCooldown[color] > 0) return { ok: false, message: `트릭스터 재사용까지 ${this.tricksterCooldown[color]}턴 남았습니다.` };
      if (card.id !== 'trickster' && this.usedCards[color]) return { ok: false, message: '이미 사용한 기술 카드입니다.' };
      if (MOVE_SKILL_CARDS.has(card.id)) {
        this.activeCardArmed[color] = card.id;
        return { ok: true, message: `${card.name} 발동 준비! 기술 이동할 말을 선택하세요.` };
      }
      if (card.id === 'iron_empress') {
        const square = this.reviveSquare(color);
        if (!this.queenReviveWindow[color]) return { ok: false, message: '퀸이 죽은 바로 다음 턴에만 사용할 수 있습니다.' };
        if (!square || this.board[square[0]][square[1]]) return { ok: false, message: '킹 앞 부활 칸이 비어 있지 않습니다.' };
        if (!this.captured[color].includes('Q')) return { ok: false, message: '부활시킬 퀸이 잡힌 말 목록에 없습니다.' };
        const knightSquare = this.findOwnPiece(color, 'N');
        if (!knightSquare) return { ok: false, message: '대신 지울 아군 나이트가 없습니다.' };
        this.board[knightSquare[0]][knightSquare[1]] = null;
        this.captured[color].splice(this.captured[color].indexOf('Q'), 1);
        this.board[square[0]][square[1]] = `${color}Q`;
        this.queenReviveWindow[color] = false;
        this.consumeCard(color);
        this.moveLog.push(`${color} card:${card.name}`);
        return { ok: true, message: `${card.name} 발동!` };
      }
      return { ok: false, message: '아직 구현되지 않은 카드입니다.' };
    }

    findOwnPiece(color, kind) {
      for (let r = 0; r < 8; r += 1) {
        for (let c = 0; c < 8; c += 1) {
          if (this.board[r][c] === `${color}${kind}`) return [r, c];
        }
      }
      return null;
    }

    nearestEmptySquare(row, col) {
      for (let radius = 1; radius < 8; radius += 1) {
        for (let r = row - radius; r <= row + radius; r += 1) {
          for (let c = col - radius; c <= col + radius; c += 1) {
            if (inBounds(r, c) && !this.board[r][c] && !(r === row && c === col)) return [r, c];
          }
        }
      }
      return null;
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
      if (action.kind === 'revive') return { P: 60, N: 130, Q: 220, R: 170 }[action.revive.piece] || 0;
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


  class AudioManager {
    constructor() {
      this.context = null;
      this.bgmTimer = null;
      this.bgmStep = 0;
      this.lastIntensity = -1;
    }
    ensure() {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (!AudioContext) return null;
      if (!this.context) this.context = new AudioContext();
      if (this.context.state === 'suspended') this.context.resume();
      return this.context;
    }
    tone(frequency, duration = 0.12, type = 'sine', gain = 0.08) {
      const ctx = this.ensure();
      if (!ctx) return;
      const osc = ctx.createOscillator();
      const amp = ctx.createGain();
      osc.type = type;
      osc.frequency.value = frequency;
      amp.gain.setValueAtTime(0.0001, ctx.currentTime);
      amp.gain.exponentialRampToValueAtTime(gain, ctx.currentTime + 0.015);
      amp.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + duration);
      osc.connect(amp).connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + duration + 0.02);
    }
    play(kind) {
      const patterns = {
        move: [[440, 0], [660, 0.06]],
        capture: [[220, 0], [165, 0.05], [330, 0.1]],
        revive: [[392, 0], [523, 0.08], [784, 0.16]],
        card: [[659, 0], [880, 0.07], [1175, 0.14]]
      };
      for (const [freq, delay] of patterns[kind] || patterns.move) {
        window.setTimeout(() => this.tone(freq, 0.14, kind === 'capture' ? 'square' : 'triangle', 0.07), delay * 1000);
      }
    }
    updateBgm(totalPoints) {
      if (!this.context) return;
      const ctx = this.ensure();
      if (!ctx) return;
      const intensity = Math.min(3, Math.floor(totalPoints / 4));
      if (this.bgmTimer && intensity === this.lastIntensity) return;
      if (this.bgmTimer) window.clearInterval(this.bgmTimer);
      this.lastIntensity = intensity;
      const tempos = [1500, 1150, 850, 620];
      const progressions = [
        [261.63, 329.63, 392.0, 523.25],
        [293.66, 369.99, 440.0, 587.33],
        [329.63, 415.3, 493.88, 659.25],
        [392.0, 493.88, 587.33, 783.99]
      ];
      this.bgmTimer = window.setInterval(() => {
        const notes = progressions[intensity];
        const note = notes[this.bgmStep % notes.length];
        this.bgmStep += 1;
        this.tone(note, 0.45, 'sine', 0.025 + intensity * 0.01);
        if (intensity >= 2) this.tone(note * 2, 0.18, 'triangle', 0.012);
      }, tempos[intensity]);
    }
  }

  class ReviveChessUi {
    constructor() {
      this.game = new ChessGame();
      this.selected = null;
      this.legalTargets = new Map();
      this.computer = new ComputerPlayer('b', this.difficultyValue());
      this.audio = new AudioManager();
      this.boardEl = document.querySelector('#board');
      this.statusEl = document.querySelector('#statusText');
      this.capturedEl = document.querySelector('#capturedText');
      this.turnBadge = document.querySelector('#turnBadge');
      this.cardTextEl = document.querySelector('#cardText');
      this.activateCardButton = document.querySelector('#activateCard');
      this.reviveMeterEl = document.querySelector('#reviveMeter');
      this.reviveButtons = new Map([...document.querySelectorAll('[data-revive]')].map((button) => [button.dataset.revive, button]));
      this.bindEvents();
      this.render();
    }
    bindEvents() {
      document.querySelector('#newGame').addEventListener('click', () => this.newGame());
      document.querySelector('#enableSound').addEventListener('click', () => { this.audio.ensure(); this.audio.updateBgm(this.totalPoints()); });
      this.activateCardButton.addEventListener('click', () => this.onActivateCard());
      document.querySelector('#difficulty').addEventListener('change', () => this.newGame());
      document.querySelectorAll('input[name="opponent"]').forEach((input) => input.addEventListener('change', () => this.newGame()));
      document.querySelectorAll('[data-revive]').forEach((button) => button.addEventListener('click', () => this.onRevive(button.dataset.revive)));
    }
    opponentValue() { return document.querySelector('input[name="opponent"]:checked').value; }
    difficultyValue() { return document.querySelector('#difficulty').value; }
    totalPoints() { return this.game.points.w + this.game.points.b; }
    newGame() {
      this.game = new ChessGame();
      this.selected = null;
      this.legalTargets = new Map();
      this.game.selectedCards = randomCards();
      this.game.resetSkillState();
      this.computer = this.opponentValue() === 'COMPUTER' ? new ComputerPlayer('b', this.difficultyValue()) : null;
      this.render();
    }
    onSquare(row, col) {
      if (this.isComputerTurn()) return;
      const key = `${row},${col}`;
      if (this.legalTargets.has(key)) {
        this.audio.ensure();
        const move = this.legalTargets.get(key);
        const wasCapture = Boolean(this.game.board[row][col]) || move.isEnPassant;
        this.game.makeMove(move);
        this.audio.play(move.skillCard ? 'card' : wasCapture ? 'capture' : 'move');
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
        this.audio.ensure();
        this.game.revive(piece);
        this.audio.play('revive');
        this.selected = null;
        this.legalTargets.clear();
        this.afterPlayerAction();
      } catch (_error) {
        alert('잡힌 말, 남은 카운트, 위치 또는 체크 상태 때문에 부활할 수 없습니다.');
      }
    }
    onActivateCard() {
      if (this.isComputerTurn()) return;
      this.audio.ensure();
      const result = this.game.activateCard(this.game.turn);
      if (!result.ok) {
        alert(result.message);
        return;
      }
      this.audio.play('card');
      this.render();
      this.maybeFinish();
    }
    afterPlayerAction() {
      this.render();
      this.maybeFinish();
      if (this.isComputerTurn()) window.setTimeout(() => this.computerTurn(), 250);
    }
    computerTurn() {
      if (!this.isComputerTurn()) return;
      const card = this.game.selectedCard(this.game.turn);
      if (card && !isPassiveCard(card) && !this.game.usedCards[this.game.turn]) {
        const cardResult = this.game.activateCard(this.game.turn);
        if (cardResult.ok) this.audio.play('card');
      }
      const action = this.computer.chooseAction(this.game);
      if (action.kind === 'move') {
        const [er, ec] = action.move.end;
        const wasCapture = Boolean(this.game.board[er][ec]) || action.move.isEnPassant;
        this.game.makeMove(action.move);
        this.audio.play(action.move.skillCard ? 'card' : wasCapture ? 'capture' : 'move');
      }
      if (action.kind === 'revive') {
        this.game.revive(action.revive.piece);
        this.audio.play('revive');
      }
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
      this.cardTextEl.textContent = this.cardStatusText();
      const currentCard = this.game.selectedCard(this.game.turn);
      this.activateCardButton.disabled = this.isComputerTurn() || isPassiveCard(currentCard) || this.game.activeCardArmed[this.game.turn] || (currentCard?.id === 'trickster' ? this.game.tricksterCooldown[this.game.turn] > 0 : this.game.usedCards[this.game.turn]);
      this.audio.updateBgm(this.totalPoints());
      this.capturedEl.textContent = `Captured allies available for revive\nWhite: ${JSON.stringify(this.game.captured.w)}\nBlack: ${JSON.stringify(this.game.captured.b)}\nRevive counters W: ${this.reviveCounterText('w')}\nRevive counters B: ${this.reviveCounterText('b')}`;
      this.updateReviveButtons();
      this.renderReviveMeter();
    }
    cardStatusText() {
      const line = (color, label) => {
        const card = this.game.selectedCard(color);
        const state = this.cardUseState(color, card);
        return `${label}: ${card?.name || '-'} · ${cardKind(card)}${card?.uses ? ` · ${card.uses}` : ''} · ${state}
${card?.description || ''}`;
      };
      return `${line('w', 'White')}

${line('b', 'Black')}`;
    }
    cardUseState(color, card) {
      if (!card) return '-';
      if (this.game.activeCardArmed[color]) return '발동 중';
      if (card.id === 'trickster' && this.game.tricksterCooldown[color] > 0) return `${this.game.tricksterCooldown[color]}턴 후 사용 가능`;
      if (isPassiveCard(card)) return this.game.usedCards[color] ? '적용 완료' : '상시 적용';
      return this.game.usedCards[color] ? '사용 완료' : '사용 가능';
    }
    reviveRemaining(color) {
      return Math.max(0, this.game.effectiveReviveLimit(color) - this.game.revivesUsed[color]);
    }
    reviveCounterText(color) {
      return `${this.reviveMeterHtml(color)} (${this.game.revivesUsed[color]}/${this.game.effectiveReviveLimit(color)})`;
    }
    reviveMeterHtml(color) {
      return [...Array(this.game.effectiveReviveLimit(color))].map((_, index) => index < this.game.revivesUsed[color] ? '●' : '○').join('');
    }
    renderReviveMeter() {
      this.reviveMeterEl.innerHTML = '';
      for (let index = 0; index < this.game.effectiveReviveLimit(this.game.turn); index += 1) {
        const circle = document.createElement('span');
        circle.className = `meter-circle ${index < this.game.revivesUsed[this.game.turn] ? 'used' : 'empty'}`;
        this.reviveMeterEl.append(circle);
      }
    }
    updateReviveButtons() {
      const legalPieces = new Set(this.game.legalRevives(this.game.turn).map((action) => action.piece));
      const inCheck = this.game.inCheck(this.game.turn);
      for (const [piece, button] of this.reviveButtons.entries()) {
        const remaining = this.reviveRemaining(this.game.turn);
        const exhausted = remaining < COSTS[piece];
        button.textContent = `${NAMES[piece]} · ${COSTS[piece]}칸 · 남은 ${remaining}칸`;
        button.classList.toggle('spent', exhausted);
        button.disabled = exhausted || inCheck || !legalPieces.has(piece) || this.isComputerTurn();
        button.title = inCheck ? '체크 상태에서는 부활할 수 없습니다.' : exhausted ? '남은 부활 카운트가 부족합니다.' : '';
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

  window.ReviveChess = { ChessGame, ComputerPlayer, Move, SKILL_CARDS };
  window.addEventListener('DOMContentLoaded', () => new ReviveChessUi());
})();
