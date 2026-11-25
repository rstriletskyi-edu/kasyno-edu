import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.configs.settings import get_settings
from src.middlewares.security import RateLimiterMiddleware, SecurityHeadersMiddleware
from src.routes import auth, blackjack, flashcards, health, llm, ruleta, slots
from src.services.flashcard_service import FlashcardService
from src.services.games.blackjack_service import BlackjackSessionStore
from src.services.llm.evaluation_service import EvaluationService
from src.services.firebase_service import init_firebase
from src.utils.exceptions import AppError

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_firebase(get_settings())
    yield


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers
    )


def create_app(rate_limit_max: int = 100, rate_limit_window: int = 60) -> FastAPI:
    settings = get_settings()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        RateLimiterMiddleware, max_requests=rate_limit_max, window_seconds=rate_limit_window
    )

    app.add_exception_handler(AppError, app_error_handler)

    app.state.evaluation_service = EvaluationService(
        settings, FlashcardService(settings.questions_path)
    )
    app.state.blackjack_store = BlackjackSessionStore()
    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(auth.router, prefix=settings.api_prefix)
    app.include_router(flashcards.router, prefix=settings.api_prefix)
    app.include_router(llm.router, prefix=settings.api_prefix)
    app.include_router(ruleta.router, prefix=settings.api_prefix)
    app.include_router(slots.router, prefix=settings.api_prefix)
    app.include_router(blackjack.router, prefix=settings.api_prefix)

    return app


app = create_app()
