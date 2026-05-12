import logging

import chess
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.model.position import EndgamePosition
from app.schema.position import CombinationResponse, MoveRequest, MoveResponse, PositionResponse
from app.service.metrics import endgame_move_errors_total, endgame_move_total
from app.service.move import OpponentMoveNotFound, PositionNotInTablebase, play_move

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/combinations", response_model=list[CombinationResponse])
def get_combinations(db: Session = Depends(get_db)):
    rows = db.query(
        EndgamePosition.combination,
        func.count().label("count"),
    ).group_by(EndgamePosition.combination).all()

    return [{"combination": r.combination, "count": r.count} for r in rows]


@router.get("/positions/random", response_model=PositionResponse)
def get_random_position(
    combination: str = Query(..., max_length=10, pattern=r"^[KQRBNPkqrbnp]+$"),
    db: Session = Depends(get_db),
):
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
    try:
        board = chess.Board(req.fen)
        if not board.is_valid():
            raise ValueError
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid FEN")

    if board.is_game_over():
        raise HTTPException(status_code=400, detail="Game is already over")

    try:
        move = chess.Move.from_uci(req.move)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid move format")

    if move not in board.legal_moves:
        raise HTTPException(status_code=400, detail="Illegal move")

    try:
        result = play_move(board, move)
    except PositionNotInTablebase:
        endgame_move_errors_total.labels(reason="position_not_in_tablebase").inc()
        raise HTTPException(status_code=400, detail="Position not found in tablebase")
    except OpponentMoveNotFound:
        endgame_move_errors_total.labels(reason="opponent_move_not_found").inc()
        logger.exception("OpponentMoveNotFound fen=%r move=%r", req.fen, req.move)
        raise HTTPException(status_code=500, detail="Failed to find opponent move")

    endgame_move_total.labels(outcome=result.outcome).inc()

    if result.outcome == "checkmate":
        return MoveResponse(status="checkmate", fen=result.fen)
    if result.outcome == "continue":
        return MoveResponse(status="continue", fen=result.fen, opponent_move=result.opponent_move)
    return MoveResponse(status="failed", fen=result.fen, reason=result.outcome)
