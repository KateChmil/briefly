from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import Base, engine
from .routers import (
    artifacts,
    calendar,
    catch_up,
    chat,
    notes,
    sources,
    spaces,
    teams,
)
from .services.generation import recover_stuck_spaces

Base.metadata.create_all(engine)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # A restart kills any in-flight generation job; don't leave spaces stuck.
    recover_stuck_spaces()
    yield


app = FastAPI(title="Briefly API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (
    spaces.router,
    sources.router,
    teams.router,
    chat.router,
    artifacts.router,
    calendar.router,
    notes.router,
    catch_up.router,
):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"status": "ok"}
