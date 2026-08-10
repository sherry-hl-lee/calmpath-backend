from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import DatabaseSettings, cors_allowed_origins, data_source_from_environment
from app.routes.api import router
from app.services.data_service import RdsRepository
from app.services.fake_repository import FakeRepository
from app.services.routing_service import RoutingService


def create_repository():
    data_source = data_source_from_environment()
    if data_source == "fake":
        repository = FakeRepository()
    elif data_source == "rds":
        repository = RdsRepository(DatabaseSettings.from_environment())
    else:  # Defensive guard; config validation should make this unreachable.
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
    title="Sensory Friendly Routing API",
    version="0.1.0",
    description="Crowd-aware walking-route comparison in Melbourne using fake or RDS data.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.get("/")
def root():
    return {"message": "Sensory Friendly Routing Backend", "docs": "/docs"}


app.include_router(router, prefix="/api/v1")
