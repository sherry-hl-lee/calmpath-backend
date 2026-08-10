from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.refuges import router as refuge_router
from app.api.routes.routing import router as routing_router
from app.core.routing_config import (
    DatabaseSettings,
    cors_allowed_origins,
    data_source_from_environment,
)
from app.services.data_service import RdsRepository
from app.services.fake_repository import FakeRepository
from app.services.routing_service import RoutingService


def create_repository():
    """Build the routing repository selected for this deployment."""

    data_source = data_source_from_environment()
    if data_source == "fake":
        repository = FakeRepository()
    elif data_source == "rds":
        repository = RdsRepository(DatabaseSettings.from_environment())
    else:  # Defensive guard; configuration validation makes this unreachable.
        raise RuntimeError(f"Unsupported DATA_SOURCE {data_source!r}.")
    repository.load()
    return repository


@asynccontextmanager
async def lifespan(app: FastAPI):
    repository = create_repository()
    app.state.repository = repository
    app.state.routing_service = RoutingService(repository)
    yield


app = FastAPI(
    title="CalmPath Backend",
    version="0.1.0",
    description="Refuge discovery and crowd-aware walking routes in Melbourne.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Stable liveness endpoint used by the existing deployment."""

    return {"status": "ok"}


app.include_router(refuge_router)
app.include_router(routing_router)
