# Zugzwang

Syzygy 테이블베이스 기반 체스 엔드게임 트레이너 API

## Overview

5기물 이하 Syzygy 테이블베이스를 활용하여 엔드게임 포지션을 제공하고, 사용자가 체크메이트까지 수를 두는 훈련 기능을 제공하는 백엔드 API 서버입니다.

- 플레이어는 항상 백으로 플레이
- 상대(흑)는 테이블베이스 기반 최선의 수로 응수
- 승리를 놓치면(무승부/패배 포지션) 즉시 실패 처리

## Tech Stack

- **Python** + **FastAPI**
- **MySQL** (Docker)
- **python-chess** + **Syzygy tablebase**
- **SQLAlchemy** + **Alembic**
- **Poetry**

## Setup

```bash
# 의존성 설치
poetry install

# Docker 실행 (MySQL + API)
docker compose up -d

# DB 마이그레이션
DATABASE_URL=mysql+pymysql://zugzwang:zugzwang@localhost:3307/zugzwang \
poetry run alembic upgrade head

# 포지션 생성 (예: KQK 1000개)
DATABASE_URL=mysql+pymysql://zugzwang:zugzwang@localhost:3307/zugzwang \
poetry run python scripts/generate.py KQK 1000
```

## API

### GET /combinations

조합 목록 조회

```json
[
  {"combination": "KQK", "count": 1000},
  {"combination": "KRK", "count": 1000}
]
```

### GET /positions/random?combination=KQK

랜덤 포지션 제공

```json
{
  "position_id": 42,
  "combination": "KQK",
  "fen": "8/8/4K1Q1/8/8/8/3k4/8 w - - 0 1"
}
```

### POST /move

착수 + 판정 + 상대 응수

Request:
```json
{
  "position_id": 42,
  "fen": "8/8/4K1Q1/8/8/8/3k4/8 w - - 0 1",
  "move": "g6d3"
}
```

Response:
```json
{"status": "continue", "fen": "...", "opponent_move": "d2c1"}
{"status": "checkmate", "fen": "..."}
{"status": "failed", "fen": "...", "reason": "draw"}
```

## Supported Combinations

| Category | Combinations |
|---|---|
| Basic Checkmate | KQK, KRK, KBBK, KBNK, KRRK, KQRK |
| Queen vs Piece | KQKR, KQKB, KQKN |
| Rook vs Piece | KRKB, KRKN |
| Pawn Endgame | KPK, KPKP, KPPKP |

## License

GPL-3.0
