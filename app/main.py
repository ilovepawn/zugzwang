from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.endgame import router as endgame_router

app = FastAPI(
    title="Zugzwang",
    description="Endgame trainer API powered by Syzygy tablebase",
)

app.include_router(endgame_router)

Instrumentator(excluded_handlers=["/metrics", "/health"]).instrument(app).expose(app)


@app.get("/health")
def health_check():
    return {"status": "ok"}
