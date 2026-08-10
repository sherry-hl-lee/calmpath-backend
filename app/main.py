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
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
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
from app.api.routes.routes import router as route_router

app.include_router(refuge_router)
app.include_router(route_router)
