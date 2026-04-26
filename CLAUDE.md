# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Zugzwang is an endgame trainer backend API for the ilovepawn chess platform. It uses local Syzygy tablebases (5 pieces or fewer) to provide winning endgame positions and evaluate moves with mathematically perfect accuracy. The player always plays as White; the opponent (Black) responds with the strongest possible defense from the tablebase.

This is one microservice in the ilovepawn MSA architecture. It exposes REST APIs only — no WebSocket. The API Gateway routes `/api/ilovepawn/endgame` requests to this service.

## Commands

```bash
# Install dependencies
poetry install

# Start MySQL + API server
docker compose up -d

# Start with rebuild
docker compose up --build -d

# Stop and remove volumes (full reset)
docker compose down -v

# Run DB migration (use port 3307 — host port mapped to container's 3306)
DATABASE_URL=mysql+pymysql://zugzwang:zugzwang@localhost:3307/zugzwang poetry run alembic upgrade head

# Generate new migration after model changes
DATABASE_URL=mysql+pymysql://zugzwang:zugzwang@localhost:3307/zugzwang poetry run alembic revision --autogenerate -m "description"

# Generate endgame positions (combination name + count)
DATABASE_URL=mysql+pymysql://zugzwang:zugzwang@localhost:3307/zugzwang poetry run python scripts/generate.py KQK 1000

# Run API server locally (without Docker)
DATABASE_URL=mysql+pymysql://zugzwang:zugzwang@localhost:3307/zugzwang poetry run uvicorn app.main:app --port 8000
```

## Architecture

**API layer** (`app/api/`) → **Schema layer** (`app/schema/`) → **Service layer** (`app/service/`) → **Model layer** (`app/model/`)

- `app/api/endgame.py` — Three endpoints: `GET /combinations`, `GET /positions/random`, `POST /move`
- `app/service/tablebase.py` — Opens Syzygy tablebase at startup (module-level singleton). Provides `probe_wdl()` and `best_opponent_move()` which iterates all legal moves and picks the one with highest DTZ (longest defense)
- `app/model/position.py` — Single table `endgame_position` with `fen` column using `utf8mb4_bin` collation (case-sensitive, required because FEN uses case to distinguish White/Black pieces)
- `scripts/generate.py` — Standalone script (uses pymysql directly, not SQLAlchemy ORM) that parses combination names like "KQK" or "KQKR" to determine piece placement, validates via tablebase, and inserts with `SELECT` dedup check before `INSERT`

## Key Technical Details

- **Syzygy files** are in `syzygy/` (gitignored, ~1GB). Downloaded from `https://tablebase.lichess.ovh/tables/standard/`. Required for both the API server and the generation script.
- **MySQL collation**: The `fen` column must use `utf8mb4_bin`, not the MySQL default `utf8mb4_0900_ai_ci`. The default is case-insensitive and treats `K` (White King) and `k` (Black King) as identical, causing false duplicate key errors.
- **Docker port mapping**: MySQL container maps `3307:3306` because the host may already have MySQL on 3306. Inside Docker Compose, services connect via `db:3306`.
- **WDL values** from Syzygy: 2 (win), 1 (cursed win), 0 (draw), -1 (blessed loss), -2 (loss). Only positions with WDL=2 are stored. The `/move` endpoint checks WDL from the side-to-move's perspective after the user's move.
- **Docker startup**: `entrypoint.sh` runs `alembic upgrade head` before uvicorn. No need to manually run migrations.
- **DB connection pool**: `pool_pre_ping=True` is set to handle stale MySQL connections after idle periods.
- **Tablebase startup check**: `app/service/tablebase.py` validates that syzygy files exist before opening. Missing files cause a clear error message and exit.
- **Input validation**: `MoveRequest.fen` (max 100 chars), `MoveRequest.move` (max 5 chars). `MoveResponse.status` and `reason` use `Literal` types.
- **Commit messages**: English, conventional commit style (feat/fix/chore/docs).
- **License**: GPL-3.0-or-later (required by python-chess dependency).
