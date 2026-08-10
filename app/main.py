from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import DatabaseSettings
from app.routes.api import router
from app.services.data_service import RdsRepository
from app.services.routing_service import RoutingService


@asynccontextmanager
async def lifespan(app: FastAPI):
    repository = RdsRepository(DatabaseSettings.from_environment())
    repository.load()
    app.state.repository = repository
    app.state.routing_service = RoutingService(repository)
    yield


app = FastAPI(
    title="Sensory Friendly Routing API",
    version="0.1.0",
    description="CSV-backed prototype for crowd-aware walking-route comparison in Melbourne.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "Sensory Friendly Routing Backend", "docs": "/docs"}


app.include_router(router)
