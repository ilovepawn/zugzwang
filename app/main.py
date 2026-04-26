from fastapi import FastAPI

from app.api.endgame import router as endgame_router

app = FastAPI(
    title="Zugzwang",
    description="Endgame trainer API powered by Syzygy tablebase",
)

app.include_router(endgame_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
