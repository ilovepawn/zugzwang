# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Zugzwang is an endgame trainer backend API for the ilovepawn chess platform. It uses local Syzygy tablebases (5 pieces or fewer) to provide winning endgame positions and evaluate moves with mathematically perfect accuracy. The player always plays as White; the opponent (Black) responds with the strongest possible defense from the tablebase.

This is one microservice in the ilovepawn MSA architecture. It exposes REST APIs only — no WebSocket. The API Gateway routes `/api/ilovepawn/endgame` requests to this service.

## Commands

Infra split: shared services (RabbitMQ, MinIO, Keycloak) live in [`ilovepawn/infra`](https://github.com/ilovepawn/infra) on the external Docker network `ilovepawn-net`. The zugzwang-local `docker-compose.yml` splits networking into two: the API attaches to both `ilovepawn-net` (for cross-stack reach) and a private `zugzwang-internal` (`internal: true`) network, while the DB attaches only to `zugzwang-internal`. This enforces database-per-service isolation at the network level — other ilovepawn services cannot connect to the zugzwang DB container. The DB has no host port mapping either: `internal: true` blocks host port publish along with external egress, so DB inspection and dev workflows run through `docker exec` against the api/db containers.

The `ilovepawn-net` network is declared `external: true` in every compose file and is not created by any of them. Create it once before bringing any stack up:

```bash
docker network create ilovepawn-net
```

```bash
# Bring up local stack (api + db) — connects to ilovepawn-net
docker compose up -d

# Install dev dependencies (pytest, httpx) for running tests on the host
poetry install --with dev

# Run tests (uses sqlite in-memory via conftest.py — no DB container needed)
poetry run pytest

# Apply DB migrations (entrypoint.sh runs this automatically on `docker compose up`;
# this is for manual re-runs)
docker exec ilovepawn-zugzwang-api-1 alembic upgrade head

# Generate new migration after model changes (the file lands inside the container;
# `docker cp` it back to host alembic/versions/ or bind-mount the directory)
docker exec ilovepawn-zugzwang-api-1 alembic revision --autogenerate -m "description"

# Generate endgame positions (combination name + count)
docker exec ilovepawn-zugzwang-api-1 python scripts/generate.py KQK 1000

# Inspect the DB directly
docker exec -it ilovepawn-zugzwang-db-1 mysql -uzugzwang -pzugzwang zugzwang
```

## Architecture

**API layer** (`app/api/`) → **Schema layer** (`app/schema/`) → **Service layer** (`app/service/`) → **Model layer** (`app/model/`)

- `app/api/endgame.py` — Four endpoints: `GET /combinations`, `GET /positions/random`, `GET /positions/{position_id}`, `POST /move`. `make_move` is a thin controller (input validation + metric inc + response dispatch); domain logic lives in `app/service/move.py`.
- `app/service/move.py` — Pure domain logic for `/move`. `play_move(board, move)` applies a validated move and returns `MoveResult(outcome, fen, opponent_move)`. Raises `PositionNotInTablebase` / `OpponentMoveNotFound` so the controller maps to HTTP 400/500.
- `app/service/tablebase.py` — Opens Syzygy tablebase at startup (module-level singleton). Provides `probe_wdl()` and `best_opponent_move()` which iterates all legal moves and picks the one with highest DTZ (longest defense). All probe calls are serialized through a module-level `threading.Lock` because `chess.syzygy.Tablebase` is not thread-safe and FastAPI sync routes are dispatched to a thread pool.
- `app/service/metrics.py` — Prometheus domain metrics: `tablebase_operation_seconds` Histogram (labeled by `operation`) and `endgame_move_total` Counter (labeled by `outcome`)
- `app/model/position.py` — Single table `endgame_position` with `fen` column using `utf8mb4_bin` collation (case-sensitive, required because FEN uses case to distinguish White/Black pieces)
- `scripts/generate.py` — Standalone script (uses pymysql directly, not SQLAlchemy ORM) that parses combination names like "KQK" or "KQKR" to determine piece placement, validates via tablebase, and inserts with `SELECT` dedup check before `INSERT`
- `tests/test_move_api.py`, `tests/test_play_move.py` — pytest suite for `/move`. API tests hit `POST /move` via FastAPI `TestClient`; domain tests call `play_move()` directly. Both require the local Syzygy tablebase files (the `app.service.tablebase` module loads them at import time).
- `tests/test_db_api.py` — pytest suite for DB-backed endpoints (`/combinations`, `/positions/random`, `/positions/{id}`). Uses the `client` fixture from `tests/conftest.py` which swaps SQLAlchemy to in-memory SQLite via `app.dependency_overrides[get_db]`. The conftest registers a `utf8mb4_bin` collation and a `rand()` function on the SQLite connection so the production model and `func.rand()` query work unchanged.
- `.github/workflows/test.yml` — CI on every push/PR. Installs deps, downloads 3-piece Syzygy (≈56KB, cached) from lichess CDN, runs `pytest`. Uses `DATABASE_URL=sqlite:///dummy` since real DB is overridden in tests.

## Key Technical Details

- **Syzygy files** are in `syzygy/` (gitignored, ~1GB). Downloaded from `https://tablebase.lichess.ovh/tables/standard/`. Required for both the API server and the generation script.
- **MySQL collation**: The `fen` column must use `utf8mb4_bin`, not the MySQL default `utf8mb4_0900_ai_ci`. The default is case-insensitive and treats `K` (White King) and `k` (Black King) as identical, causing false duplicate key errors.
- **WDL values** from Syzygy: 2 (win), 1 (cursed win), 0 (draw), -1 (blessed loss), -2 (loss). Only positions with WDL=2 are stored. After the user's move, `/move` probes WDL from the side-to-move's perspective (Black). Only `WDL == -2` (clean loss for Black = clean win for White) continues the game — `WDL == -1` is treated as `failed/lost` because the user is now in cursed-win territory where the 50-move rule reduces it to a draw, so the winning advantage is effectively gone.
- **Container startup**: `entrypoint.sh` runs `alembic upgrade head` before uvicorn. No need to manually run migrations when running via `docker compose up`.
- **Network alias & healthcheck warmup**: The `api` service registers the alias `zugzwang-api` on `ilovepawn-net` so external stacks (future Nginx gateway, Prometheus in `ilovepawn/infra`) resolve it by a stable name without depending on the auto-generated `ilovepawn-zugzwang-api-1`. Aliases are preferred over `container_name` because they keep replica scaling possible. The api healthcheck includes `start_period: 30s` to absorb the alembic migration window on cold start before counting failures.
- **DB connection pool**: `pool_pre_ping=True` is set to handle stale MySQL connections after idle periods.
- **Tablebase startup check**: `app/service/tablebase.py` validates that syzygy files exist before opening. Missing files cause a clear error message and exit.
- **Settings & env**: `app/config.py`'s `Settings` reads `DATABASE_URL` (required) and `SYZYGY_PATH` directly from process environment — no `.env` file is used. Docker compose injects them via the `environment:` block; tests bootstrap `sqlite:///dummy` via `os.environ.setdefault` at the top of `tests/conftest.py` (the real DB is overridden by the SQLite fixture anyway).
- **Input validation**: `MoveRequest.fen` (max 100 chars), `MoveRequest.move` (max 5 chars). `MoveResponse.status` and `reason` use `Literal` types. `/positions/random` validates `combination` via FastAPI `Query(..., max_length=10, pattern=r"^[KQRBNPkqrbnp]+$")` before the `.upper()` normalization.
- **`pymysql[rsa]` extras**: MySQL 8.x default authentication (`caching_sha2_password`) requires `cryptography`, which `pymysql` only pulls in via the `[rsa]` extras. Do not strip the brackets when editing `pyproject.toml`.
- **Poetry package mode**: `pyproject.toml` sets `[tool.poetry] package-mode = false`. The project's import root is `app/`, not `zugzwang/`, so Poetry's package autodetection would fail. Setting `package-mode = false` uses Poetry purely for dependency management — no wheel build, no "No file/folder found for package zugzwang" error.
- **Pytest configuration**: `pyproject.toml` includes `[tool.pytest.ini_options]` with `testpaths = ["tests"]` and `pythonpath = ["."]` so `from app.main import app` resolves. `tests/conftest.py` carries DB fixtures (SQLite in-memory + dialect adapters).
- **Global exception handler & logging**: `app/main.py` configures `logging.basicConfig` and registers `@app.exception_handler(Exception)` that logs the traceback with the request method/path before returning a generic 500. The `/move` controller additionally logs FEN/move context on `OpponentMoveNotFound`.
- **Prometheus metrics**: `prometheus-fastapi-instrumentator` exposes `/metrics` and auto-collects HTTP request count/latency/in-progress. `/metrics` and `/health` are passed to `excluded_handlers` so scrape and health-check traffic don't pollute the HTTP metrics. Custom domain metrics in `app/service/metrics.py`: `tablebase_operation_seconds` uses sub-millisecond buckets `(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0)` because Syzygy probes complete in microseconds — the prometheus_client default buckets (starting at 5ms) collapse all measurements into one bucket and make quantiles meaningless. `endgame_move_total` is labeled by outcome (`checkmate`, `continue`, `stalemate`, `draw`, `lost`).
- **Commit messages**: English, conventional commit style (feat/fix/chore/docs).
- **License**: GPL-3.0-or-later (required by python-chess dependency).
