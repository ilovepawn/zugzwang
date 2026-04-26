from pydantic import BaseModel


class CombinationResponse(BaseModel):
    combination: str
    count: int


class PositionResponse(BaseModel):
    position_id: int
    combination: str
    fen: str


class MoveRequest(BaseModel):
    position_id: int
    fen: str
    move: str


class MoveResponse(BaseModel):
    status: str
    fen: str
    opponent_move: str | None = None
    reason: str | None = None
