# Zugzwang

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![MySQL](https://img.shields.io/badge/MySQL-8.4-4479A1?logo=mysql&logoColor=white)](https://www.mysql.com/)
[![License](https://img.shields.io/badge/License-GPL--3.0--or--later-blue)](LICENSE)

[한국어](README.ko.md)

> *Zugzwang (n.)* — A situation in chess where the obligation to make a move is a disadvantage.

**Endgame Trainer API** for the [ilovepawn](https://github.com/ilovepawn) chess platform, powered by Syzygy endgame tablebases.

Train your endgame technique against a perfectly playing opponent. Every response is mathematically optimal — backed by 5-piece Syzygy tablebases containing over 14,000 pre-validated winning positions.

---

## How It Works

1. Pick an endgame combination (e.g. King + Rook vs King)
2. Receive a random winning position — you play as **White**
3. Make your move — the opponent responds with the **strongest defense**
4. Deliver checkmate to win, or lose the advantage and fail

The opponent's moves are sourced directly from Syzygy tablebases, meaning every defense is the absolute best possible. If you can win here, you can win anywhere.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI |
| Chess Engine | python-chess + Syzygy tablebase |
| Database | MySQL 8.4 LTS |
| ORM / Migration | SQLAlchemy + Alembic |
| Package Manager | Poetry |
| Infrastructure | Docker + Docker Compose |

---

## Getting Started

### Prerequisites

- Python 3.13+
- Docker & Docker Compose
- [Syzygy 3-4-5 tablebase files](https://tablebase.lichess.ovh/tables/standard/) in `syzygy/`

### Run

```bash
# Install dependencies
poetry install

# Start MySQL + API server
docker compose up -d

# Run database migration
DATABASE_URL=mysql+pymysql://zugzwang:zugzwang@localhost:3307/zugzwang \
  poetry run alembic upgrade head

# Generate positions (combination, count)
DATABASE_URL=mysql+pymysql://zugzwang:zugzwang@localhost:3307/zugzwang \
  poetry run python scripts/generate.py KQK 1000
```

---

## API Reference

### `GET /combinations`

Returns available endgame combinations with position counts.

```json
[
  { "combination": "KQK", "count": 1000 },
  { "combination": "KRK", "count": 1000 }
]
```

### `GET /positions/random?combination={combo}`

Returns a random winning position for the given combination.

```json
{
  "combination": "KQK",
  "fen": "8/8/4K1Q1/8/8/8/3k4/8 w - - 0 1"
}
```

### `POST /move`

Submit a move and receive the judgment + opponent's response.

**Request**
```json
{
  "fen": "8/8/4K1Q1/8/8/8/3k4/8 w - - 0 1",
  "move": "g6d3"
}
```

**Response**

| status | Description |
|---|---|
| `continue` | Valid winning move. Includes `opponent_move` and updated `fen`. |
| `checkmate` | Checkmate delivered. You win. |
| `failed` | Winning advantage lost. Includes `reason`: `draw`, `lost`, or `stalemate`. |

---

## Supported Combinations

| Category | Combinations | Description |
|---|---|---|
| Basic Checkmate | KQK, KRK, KBBK, KBNK, KRRK, KQRK | Deliver checkmate with major/minor pieces |
| Queen vs Piece | KQKR, KQKB, KQKN | Win with queen against a single defender |
| Rook vs Piece | KRKB, KRKN | Win with rook against a single defender |
| Pawn Endgame | KPK, KPKP, KPPKP | Promote and win in pawn endgames |

---

## Project Structure

```
zugzwang/
├── app/
│   ├── api/           # API endpoints
│   ├── model/         # Database models
│   ├── schema/        # Request/Response DTOs
│   ├── service/       # Tablebase probing logic
│   ├── config.py      # Environment configuration
│   ├── database.py    # Database connection
│   └── main.py        # FastAPI entrypoint
├── alembic/           # Database migrations
├── scripts/           # Position generation script
├── syzygy/            # Syzygy tablebase files (not tracked in git)
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

---

## License

This project is licensed under the **GPL-3.0-or-later License** — see the [LICENSE](LICENSE) file for details.

GPL-3.0-or-later is required due to the [python-chess](https://github.com/niklasf/python-chess) dependency.
