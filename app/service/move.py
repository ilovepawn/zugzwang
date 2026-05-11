from dataclasses import dataclass
from typing import Literal

import chess

from app.service.tablebase import best_opponent_move, probe_wdl

Outcome = Literal["checkmate", "continue", "stalemate", "draw", "lost"]


@dataclass
class MoveResult:
    outcome: Outcome
    fen: str
    opponent_move: str | None = None


class PositionNotInTablebase(Exception):
    pass


class OpponentMoveNotFound(Exception):
    pass


def play_move(board: chess.Board, move: chess.Move) -> MoveResult:
    """검증된 보드/수를 적용해 결과를 반환. 입력 검증은 호출자 책임."""
    board.push(move)

    if board.is_checkmate():
        return MoveResult("checkmate", board.fen())
    if board.is_stalemate():
        return MoveResult("stalemate", board.fen())
    if board.is_insufficient_material():
        return MoveResult("draw", board.fen())

    try:
        wdl = probe_wdl(board)
    except KeyError as e:
        raise PositionNotInTablebase from e

    # 흑 관점 WDL == -2 (clean loss)만 진행. -1(blessed loss)은 사용자가 cursed win
    # 상태 → 50수룰로 무승부 가능 → advantage 잃음으로 분류.
    if wdl > -2:
        return MoveResult("draw" if wdl == 0 else "lost", board.fen())

    opponent_move = best_opponent_move(board)
    if opponent_move is None:
        raise OpponentMoveNotFound

    board.push(opponent_move)

    if board.is_stalemate():
        return MoveResult("stalemate", board.fen())
    if board.is_insufficient_material():
        return MoveResult("draw", board.fen())

    return MoveResult("continue", board.fen(), opponent_move.uci())
