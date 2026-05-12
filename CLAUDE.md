# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Zugzwang is an endgame trainer backend API for the ilovepawn chess platform. It uses local Syzygy tablebases (5 pieces or fewer) to provide winning endgame positions and evaluate moves with mathematically perfect accuracy. The player always plays as White; the opponent (Black) responds with the strongest possible defense from the tablebase.

This is one microservice in the ilovepawn MSA architecture. It exposes REST APIs only — no WebSocket. The API Gateway routes `/api/ilovepawn/endgame` requests to this service.

## Commands

Infra split: shared services (RabbitMQ, MinIO, Keycloak) live in [`ilovepawn/infra`](https://github.com/ilovepawn/infra) on the external Docker network `ilovepawn-net`. The zugzwang-local `docker-compose.yml` splits networking into two: the API and `mysql-exporter` attach to both `ilovepawn-net` (for cross-stack reach) and a private `zugzwang-internal` (`internal: true`) network, while the DB attaches only to `zugzwang-internal`. This enforces database-per-service isolation at the network level — other ilovepawn services cannot connect to the zugzwang DB container. The DB has no host port mapping either: `internal: true` blocks host port publish along with external egress, so DB inspection and dev workflows run through `docker exec` against the api/db containers. The DB metrics path follows the same rule: the central Prometheus in `ilovepawn/infra` scrapes `zugzwang-mysql-exporter:9104` on `ilovepawn-net`, and the exporter is the only process that holds an `ilovepawn-net`↔DB bridge.

The `ilovepawn-net` network is declared `external: true` in every compose file and is not created by any of them. Create it once before bringing any stack up:

```bash
docker network create ilovepawn-net
```

```bash
# Bring up local stack (api + db + mysql-exporter) — connects to ilovepawn-net
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

# One-time exporter user setup (only for pre-existing mysql_data volumes;
# fresh volumes get it automatically from /docker-entrypoint-initdb.d)
docker exec -i ilovepawn-zugzwang-db-1 mysql -uroot -proot < db/init/01-exporter.sql
```

## Architecture

**API layer** (`app/api/`) → **Schema layer** (`app/schema/`) → **Service layer** (`app/service/`) → **Model layer** (`app/model/`)

- `app/api/endgame.py` — Four endpoints: `GET /combinations`, `GET /positions/random`, `GET /positions/{position_id}`, `POST /move`. `make_move` is a thin controller (input validation + metric inc + response dispatch); domain logic lives in `app/service/move.py`.
- `app/service/move.py` — Pure domain logic for `/move`. `play_move(board, move)` applies a validated move and returns `MoveResult(outcome, fen, opponent_move)`. Raises `PositionNotInTablebase` / `OpponentMoveNotFound` so the controller maps to HTTP 400/500.
- `app/service/tablebase.py` — Opens Syzygy tablebase at startup (module-level singleton). Provides `probe_wdl()` and `best_opponent_move()` which iterates all legal moves and picks the one with highest DTZ (longest defense). All probe calls are serialized through a module-level `threading.Lock` because `chess.syzygy.Tablebase` is not thread-safe and FastAPI sync routes are dispatched to a thread pool.
- `app/service/metrics.py` — Prometheus domain metrics: `tablebase_operation_seconds` / `tablebase_lock_wait_seconds` Histograms (both labeled by `operation`), `endgame_move_total` / `endgame_move_errors_total` Counters, `zugzwang_app_info`, and a `_DBPoolCollector` exposing `db_pool_connections{state=...}` from the live SQLAlchemy engine
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
- **Prometheus metrics**: `prometheus-fastapi-instrumentator` exposes `/metrics` and auto-collects HTTP request count/latency/in-progress. `/metrics` and `/health` are passed to `excluded_handlers` so scrape and health-check traffic don't pollute the HTTP metrics. `latency_highr_buckets` / `latency_lowr_buckets` are overridden on the instrumentator because the defaults (highr 0.01s~, lowr 0.1s~) are far too coarse — most responses land below 5ms and would collapse into the first bucket. Custom domain metrics in `app/service/metrics.py`:
  - `tablebase_operation_seconds{operation}` — Syzygy operation wall-clock latency, **lock wait included**, for both `probe_wdl` and `best_opponent_move`. Buckets start at `0.00001` (10μs) because real probes complete in tens of microseconds; the previous `0.0001` floor still collapsed everything into one bucket. The two labels share one definition ("caller-observed time for this call") so cross-label aggregation is meaningful.
  - `tablebase_lock_wait_seconds{operation}` — Time spent blocked acquiring `_tablebase_lock`. Split from `tablebase_operation_seconds` so contention is visible separately from probe cost (with a single global lock serializing all probes, "is it the lock or the probe?" is the first question during slowdowns). For `best_opponent_move`, one observation is recorded per legal-move iteration, so the histogram `_count` is N× the call count — do NOT divide `lock_wait_count / operation_count` to derive per-call lock-wait. The acquire helper guarantees lock release if the wait-time observation itself raises (e.g. signal interrupt between `acquire()` and the matching `try` block in the caller), so the lock cannot leak from instrumentation failure.
  - `endgame_move_total{outcome}` — outcomes: `checkmate`, `continue`, `stalemate`, `draw`, `lost`.
  - `endgame_move_errors_total{reason}` — `position_not_in_tablebase`, `opponent_move_not_found`. Incremented before the matching `HTTPException` so these failures are visible in domain metrics, not just in `http_requests_total{status=4xx/5xx}`.
  - `db_pool_connections{state}` — `checked_out`, `checked_in`, `overflow`, `size` from `engine.pool` via a custom `_DBPoolCollector`. `overflow` is clamped to ≥0 because SQLAlchemy's `pool.overflow()` is an internal counter that starts at `-size` until the pool fills.
  - `zugzwang_app_info{version}` — version label gauge (always `1.0`), useful for joining metric changes to deploys in Grafana.
- **MySQL metrics (`mysql-exporter` sidecar)**: `prom/mysqld-exporter:v0.15.1` runs alongside the DB and exposes MySQL metrics on `:9104/metrics` under the `ilovepawn-net` alias `zugzwang-mysql-exporter`. The exporter is the only component dual-homed on `ilovepawn-net` *and* `zugzwang-internal` — central Prometheus stays out of the private DB network, and the DB stays out of `ilovepawn-net`. It authenticates with a dedicated `exporter` MySQL user (read-only: `PROCESS, REPLICATION CLIENT, SELECT`, `MAX_USER_CONNECTIONS 3`) so the application's `zugzwang` credentials never leave the API container. The user is provisioned by `db/init/01-exporter.sql` via `/docker-entrypoint-initdb.d/` — that path **only fires on fresh volume init**, so any pre-existing `mysql_data` volume needs the manual one-shot shown in the Commands section. Password is hardcoded (`exporter`) on purpose: the exporter is unreachable from outside the two private networks, and the value matches the existing `zugzwang/zugzwang` plaintext convention for local dev. The `slave_status` scraper is disabled (`--no-collect.slave_status`) because MySQL 8.4 renamed `SHOW SLAVE STATUS` → `SHOW REPLICA STATUS` and mysqld_exporter v0.15.1 still emits the legacy syntax; leaving it enabled produces a recurring `Error 1064` per scrape. We don't run replication, so the scraper provides no useful signal anyway.
- **Commit messages**: English, conventional commit style (feat/fix/chore/docs).
- **License**: GPL-3.0-or-later (required by python-chess dependency).
