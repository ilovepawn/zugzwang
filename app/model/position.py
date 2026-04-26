from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EndgamePosition(Base):
    __tablename__ = "endgame_position"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    combination: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    fen: Mapped[str] = mapped_column(String(100, collation="utf8mb4_bin"), nullable=False, unique=True)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
