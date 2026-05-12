import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.endgame import router as endgame_router
# metrics 모듈 import 시점에 DB pool collector / app_info 가 REGISTRY 에 등록되므로
# 명시적으로 한 번 로드한다 (다른 곳에서 이미 import 되지만 안전망).
import app.service.metrics  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Zugzwang",
    description="Endgame trainer API powered by Syzygy tablebase",
)

app.include_router(endgame_router)

# 디폴트 latency 버킷(highr 0.01s~ / lowr 0.1s~)이 도메인에 비해 너무 성김.
# 서브밀리초~수십ms 대역을 촘촘하게 캡처하도록 조정.
Instrumentator(
    excluded_handlers=["/metrics", "/health"],
).instrument(
    app,
    latency_lowr_buckets=(0.005, 0.01, 0.05, 0.1, 0.5, 1.0),
    latency_highr_buckets=(
        0.0005, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1,
        0.25, 0.5, 1.0, 2.5, 5.0, 10.0,
    ),
).expose(app)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health")
def health_check():
    return {"status": "ok"}
