import os
import random

os.environ.setdefault("DATABASE_URL", "sqlite:///dummy")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.model.position import EndgamePosition


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _register_sqlite_extensions(dbapi_connection, _):
        # 프로덕션 MySQL의 utf8mb4_bin / rand()를 SQLite에서 흉내내서
        # 모델·쿼리 수정 없이 같은 코드를 테스트.
        dbapi_connection.create_function("rand", 0, random.random)
        dbapi_connection.create_collation(
            "utf8mb4_bin", lambda a, b: (a > b) - (a < b)
        )

    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def seeded_positions(db_session):
    positions = [
        EndgamePosition(id=1, combination="KQK", fen="8/8/8/8/4k3/8/4K3/4Q3 w - - 0 1", difficulty=0),
        EndgamePosition(id=2, combination="KQK", fen="8/8/4K1Q1/8/8/8/3k4/8 w - - 0 1", difficulty=0),
        EndgamePosition(id=3, combination="KRK", fen="4k3/8/4K3/8/8/8/8/7R w - - 0 1", difficulty=0),
    ]
    db_session.add_all(positions)
    db_session.commit()
    for p in positions:
        db_session.refresh(p)
    return positions
