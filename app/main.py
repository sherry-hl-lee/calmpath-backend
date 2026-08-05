from fastapi import FastAPI


app = FastAPI(
    title="CalmPath Backend",
    version="0.1.0",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
from app.api.routes.refuges import router as refuge_router

app.include_router(refuge_router)
