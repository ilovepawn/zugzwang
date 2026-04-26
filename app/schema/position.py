from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class CombinationResponse(CamelModel):
    combination: str
    count: int


class PositionResponse(CamelModel):
    position_id: int
    combination: str
    fen: str


class MoveRequest(CamelModel):
    fen: str = Field(max_length=100)
    move: str = Field(max_length=5)


class MoveResponse(CamelModel):
    status: Literal["continue", "checkmate", "failed"]
    fen: str
    opponent_move: str | None = None
    reason: Literal["draw", "lost", "stalemate"] | None = None
