from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(
    title="CalmPath Backend",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://fit5120-2026s2-tp10.github.io",
        "https://calmpath-tp10.netlify.app",
    ],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
from app.api.routes.refuges import router as refuge_router

app.include_router(refuge_router)
