# Zugzwang

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![MySQL](https://img.shields.io/badge/MySQL-8.4-4479A1?logo=mysql&logoColor=white)](https://www.mysql.com/)
[![License](https://img.shields.io/badge/License-GPL--3.0--or--later-blue)](LICENSE)

[English](README.md)

> *츠크츠방크 (Zugzwang)* — 체스에서 수를 두어야만 하는 의무가 오히려 불리하게 작용하는 상황.

[ilovepawn](https://github.com/ilovepawn) 체스 플랫폼의 **엔드게임 트레이너 API**입니다. Syzygy 엔드게임 테이블베이스를 기반으로 동작합니다.

수학적으로 완벽한 상대를 두고 엔드게임 기술을 훈련하세요. 5기물 이하 Syzygy 테이블베이스로 검증된 14,000개 이상의 승리 포지션을 제공합니다.

---

## 동작 방식

1. 엔드게임 조합을 선택합니다 (예: 킹 + 룩 vs 킹)
2. 랜덤 승리 포지션을 받습니다 — 플레이어는 항상 **백**
3. 수를 두면 상대가 **최강의 수비**로 응수합니다
4. 체크메이트를 달성하면 성공, 승리를 놓치면 실패

상대의 응수는 Syzygy 테이블베이스에서 직접 가져오기 때문에, 수학적으로 가능한 최선의 수비입니다. 여기서 이길 수 있다면, 어디서든 이길 수 있습니다.

---

## 기술 스택

| 구분 | 기술 |
|---|---|
| 프레임워크 | FastAPI |
| 체스 엔진 | python-chess + Syzygy tablebase |
| 데이터베이스 | MySQL 8.4 LTS |
| ORM / 마이그레이션 | SQLAlchemy + Alembic |
| 패키지 매니저 | Poetry |
| 인프라 | Docker Compose (로컬) + [ilovepawn/infra](https://github.com/ilovepawn/infra)의 공용 서비스 |

---

## 시작하기

### 사전 요구사항

- Docker + Docker Compose
- Python 3.13+ (Docker 없이 실행할 때만 필요)
- [Syzygy 3-4-5 테이블베이스 파일](https://tablebase.lichess.ovh/tables/standard/)을 `syzygy/` 디렉토리에 배치
- 공용 Docker 네트워크 `ilovepawn-net` — 없다면 한 번만 생성:
  ```bash
  docker network create ilovepawn-net
  ```

### Docker Compose 실행 (권장)

```bash
docker compose up -d
```

MySQL(호스트 포트 `3307`)과 API(`http://localhost:8000`)가 함께 기동됩니다. API 컨테이너는 `ilovepawn-net`에 연결되어 공용 네트워크 상의 다른 서비스에 컨테이너명으로 접근할 수 있습니다. 마이그레이션은 컨테이너 기동 시 자동 실행됩니다.

### 로컬 실행 (Docker 없이)

```bash
# 의존성 설치
poetry install

# 데이터베이스 마이그레이션 (호스트 포트 3307의 도커 MySQL 대상)
DATABASE_URL=mysql+pymysql://zugzwang:zugzwang@localhost:3307/zugzwang \
  poetry run alembic upgrade head

# API 서버 실행
DATABASE_URL=mysql+pymysql://zugzwang:zugzwang@localhost:3307/zugzwang \
  poetry run uvicorn app.main:app --port 8000

# 포지션 생성 (조합명, 개수)
DATABASE_URL=mysql+pymysql://zugzwang:zugzwang@localhost:3307/zugzwang \
  poetry run python scripts/generate.py KQK 1000
```

---

## API 문서

### `GET /combinations`

사용 가능한 엔드게임 조합 목록을 반환합니다.

```json
[
  { "combination": "KQK", "count": 1000 },
  { "combination": "KRK", "count": 1000 }
]
```

### `GET /positions/random?combination={combo}`

해당 조합에서 랜덤 승리 포지션을 반환합니다.

```json
{
  "positionId": 42,
  "combination": "KQK",
  "fen": "8/8/4K1Q1/8/8/8/3k4/8 w - - 0 1"
}
```

### `GET /positions/{position_id}`

지정한 ID의 엔드게임 포지션을 반환합니다. 존재하지 않으면 `404`를 반환합니다.

```json
{
  "positionId": 42,
  "combination": "KQK",
  "fen": "8/8/4K1Q1/8/8/8/3k4/8 w - - 0 1"
}
```

### `POST /move`

수를 제출하고 판정 결과와 상대 응수를 받습니다.

**요청**
```json
{
  "fen": "8/8/4K1Q1/8/8/8/3k4/8 w - - 0 1",
  "move": "g6d3"
}
```

**응답**

| status | 설명 |
|---|---|
| `continue` | 유효한 승리 수. `opponentMove`와 업데이트된 `fen` 포함. |
| `checkmate` | 체크메이트 성공. |
| `failed` | 승리 기회 상실. `reason`: `draw`, `lost`, `stalemate` 중 하나. |

---

## 지원 조합

| 카테고리 | 조합 | 설명 |
|---|---|---|
| 기본 체크메이트 | KQK, KRK, KBBK, KBNK, KRRK, KQRK | 주요/마이너 기물로 체크메이트 |
| 퀸 vs 단일 기물 | KQKR, KQKB, KQKN | 퀸으로 단일 수비 기물 상대 승리 |
| 룩 vs 단일 기물 | KRKB, KRKN | 룩으로 단일 수비 기물 상대 승리 |
| 폰 엔딩 | KPK, KPKP, KPPKP | 폰 엔딩에서 승진하여 승리 |

---

## 프로젝트 구조

```
zugzwang/
├── app/
│   ├── api/           # API 엔드포인트
│   ├── model/         # 데이터베이스 모델
│   ├── schema/        # 요청/응답 DTO
│   ├── service/       # 테이블베이스 조회 로직
│   ├── config.py      # 환경 설정
│   ├── database.py    # 데이터베이스 연결
│   └── main.py        # FastAPI 진입점
├── alembic/           # 데이터베이스 마이그레이션
├── scripts/           # 포지션 생성 스크립트
├── syzygy/            # Syzygy 테이블베이스 파일 (git 미추적)
├── Dockerfile
└── pyproject.toml
```

---

## 라이선스

이 프로젝트는 **GPL-3.0-or-later 라이선스** 하에 배포됩니다 — 자세한 내용은 [LICENSE](LICENSE) 파일을 참고하세요.

[python-chess](https://github.com/niklasf/python-chess) 의존성으로 인해 GPL-3.0-or-later가 적용됩니다.
