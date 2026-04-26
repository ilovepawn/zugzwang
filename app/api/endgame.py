import chess
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.model.position import EndgamePosition
from app.schema.position import CombinationResponse, MoveRequest, MoveResponse, PositionResponse
from app.service.tablebase import best_opponent_move, probe_wdl

router = APIRouter()


@router.get("/combinations", response_model=list[CombinationResponse])
def get_combinations(db: Session = Depends(get_db)):
    rows = db.query(
        EndgamePosition.combination,
        func.count().label("count"),
    ).group_by(EndgamePosition.combination).all()

    return [{"combination": r.combination, "count": r.count} for r in rows]


@router.get("/positions/random", response_model=PositionResponse)
def get_random_position(combination: str, db: Session = Depends(get_db)):
    position = (
        db.query(EndgamePosition)
        .filter_by(combination=combination.upper())
        .order_by(func.rand())
        .first()
    )

    if not position:
        raise HTTPException(status_code=404, detail="No positions found for this combination")

    return {
        "position_id": position.id,
        "combination": position.combination,
        "fen": position.fen,
    }


@router.post("/move", response_model=MoveResponse)
def make_move(req: MoveRequest):
    board = chess.Board(req.fen)

    # 사용자 수 파싱
    try:
        move = chess.Move.from_uci(req.move)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid move format")

    if move not in board.legal_moves:
        raise HTTPException(status_code=400, detail="Illegal move")

    # 사용자 수 적용
    board.push(move)

    # 체크메이트 확인
    if board.is_checkmate():
        return MoveResponse(status="checkmate", fen=board.fen())

    # 테이블베이스로 WDL 조회 (흑 관점이므로 부호 반전)
    wdl = probe_wdl(board)
    if wdl >= 0:
        # 흑 관점에서 승리 또는 무승부 = 백이 승리를 놓침
        reason = "draw" if wdl == 0 else "lost"
        return MoveResponse(status="failed", fen=board.fen(), reason=reason)

    # 상대 최선의 수
    opponent_move = best_opponent_move(board)
    board.push(opponent_move)

    # 상대 수 후 스테일메이트 체크
    if board.is_stalemate():
        return MoveResponse(status="failed", fen=board.fen(), reason="stalemate")

    return MoveResponse(
        status="continue",
        fen=board.fen(),
        opponent_move=opponent_move.uci(),
    )
