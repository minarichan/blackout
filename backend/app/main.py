from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.health import router as health_router
from app.api.portfolio import router as portfolio_router
from app.api.positions import router as positions_router
from app.api.risk import router as risk_router
from app.config import get_settings
from app.db.session import init_db
from app.services.portfolio_service import AddressError, PortfolioService, RateLimitError


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(settings)
        service = PortfolioService(settings)
        app.state.service = service
        await service.start()
        try:
            yield
        finally:
            await service.stop()

    app = FastAPI(
        title="Blackout",
        summary="Cross-chain position and risk aggregator",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list or ["http://localhost:5173"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(portfolio_router)
    app.include_router(positions_router)
    app.include_router(risk_router)

    @app.get("/")
    def root() -> dict:
        return {"service": "blackout", "health": "/health", "docs": "/docs"}

    @app.exception_handler(AddressError)
    async def address_error(_, exc: AddressError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(RateLimitError)
    async def rate_error(_, exc: RateLimitError) -> JSONResponse:
        return JSONResponse(status_code=429, content={"detail": str(exc)})

    return app


app = create_app()
