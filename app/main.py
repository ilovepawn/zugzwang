from fastapi import FastAPI

app = FastAPI(
    title="Zugzwang",
    description="Endgame trainer API powered by Syzygy tablebase",
)


@app.get("/health")
def health_check():
    return {"status": "ok"}
