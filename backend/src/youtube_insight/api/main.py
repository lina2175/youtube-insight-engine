"""FastAPI application factory with explicit resource lifecycle."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from youtube_insight.config import Settings
from youtube_insight.data.database import (
    create_database_engine,
    create_session_factory,
    database_is_ready,
    initialize_database,
)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        engine = create_database_engine(settings.database_path)
        try:
            initialize_database(engine)
            application.state.engine = engine
            application.state.session_factory = create_session_factory(engine)
            yield
        finally:
            engine.dispose()

    application = FastAPI(title="YouTube Insight Engine", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET"],
        allow_headers=["Accept"],
        allow_credentials=False,
    )

    @application.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        try:
            ready = database_is_ready(application.state.engine)
        except SQLAlchemyError:
            ready = False
        if not ready:
            raise HTTPException(status_code=503, detail="Service unavailable")
        return HealthResponse()

    return application


app = create_app()
