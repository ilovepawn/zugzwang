from typing import Literal

from pydantic import BaseModel, Field


class CombinationResponse(BaseModel):
    combination: str
    count: int


class PositionResponse(BaseModel):
    combination: str
    fen: str


class MoveRequest(BaseModel):
    fen: str = Field(max_length=100)
    move: str = Field(max_length=5)


class MoveResponse(BaseModel):
    status: Literal["continue", "checkmate", "failed"]
    fen: str
    opponent_move: str | None = None
    reason: Literal["draw", "lost", "stalemate"] | None = None
