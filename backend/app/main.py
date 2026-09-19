from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import Base, engine
from .routers import artifacts, chat, sources, spaces, teams

Base.metadata.create_all(engine)

app = FastAPI(title="Briefly API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (spaces.router, sources.router, teams.router, chat.router, artifacts.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"status": "ok"}
