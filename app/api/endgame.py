import chess
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.model.position import EndgamePosition
from app.schema.position import CombinationResponse, MoveRequest, MoveResponse, PositionResponse
from app.service.metrics import endgame_move_total
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


@router.get("/positions/{position_id}", response_model=PositionResponse)
def get_position(position_id: int, db: Session = Depends(get_db)):
    position = db.query(EndgamePosition).filter_by(id=position_id).first()

    if not position:
        raise HTTPException(status_code=404, detail="Position not found")

    return {
        "position_id": position.id,
        "combination": position.combination,
        "fen": position.fen,
    }


@router.post("/move", response_model=MoveResponse)
def make_move(req: MoveRequest):
    # FEN 유효성 검증
    try:
        board = chess.Board(req.fen)
        if not board.is_valid():
            raise ValueError
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid FEN")

    # 이미 종료된 포지션 체크
    if board.is_game_over():
        raise HTTPException(status_code=400, detail="Game is already over")

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
        endgame_move_total.labels(outcome="checkmate").inc()
        return MoveResponse(status="checkmate", fen=board.fen())

    # 스테일메이트 확인
    if board.is_stalemate():
        endgame_move_total.labels(outcome="stalemate").inc()
        return MoveResponse(status="failed", fen=board.fen(), reason="stalemate")

    # 기물 부족 무승부 확인
    if board.is_insufficient_material():
        endgame_move_total.labels(outcome="draw").inc()
        return MoveResponse(status="failed", fen=board.fen(), reason="draw")

    # 테이블베이스로 WDL 조회 (사용자 수 후이므로 흑 관점)
    try:
        wdl = probe_wdl(board)
    except KeyError:
        raise HTTPException(status_code=400, detail="Position not found in tablebase")

    # 흑 관점 WDL == -2 (clean loss)만 계속 진행. WDL == -1(blessed loss)은
    # 사용자가 cursed win 상태 → 50수룰로 무승부 가능 → advantage 잃음으로 분류.
    if wdl > -2:
        reason = "draw" if wdl == 0 else "lost"
        endgame_move_total.labels(outcome=reason).inc()
        return MoveResponse(status="failed", fen=board.fen(), reason=reason)

    # 상대 최선의 수
    opponent_move = best_opponent_move(board)
    if opponent_move is None:
        raise HTTPException(status_code=500, detail="Failed to find opponent move")

    board.push(opponent_move)

    # 상대 수 후 스테일메이트 체크
    if board.is_stalemate():
        endgame_move_total.labels(outcome="stalemate").inc()
        return MoveResponse(status="failed", fen=board.fen(), reason="stalemate")

    # 상대 수 후 기물 부족 무승부 체크
    if board.is_insufficient_material():
        endgame_move_total.labels(outcome="draw").inc()
        return MoveResponse(status="failed", fen=board.fen(), reason="draw")

    endgame_move_total.labels(outcome="continue").inc()
    return MoveResponse(
        status="continue",
        fen=board.fen(),
        opponent_move=opponent_move.uci(),
    )
