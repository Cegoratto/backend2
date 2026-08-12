from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import ai, auth, billing, boards, cards, columns, profiles
from app.core.config import get_settings
from app.core.cors import is_allowed_origin
from app.db.base import Base
from app.db.session import engine
from app.db.sqlite_migrations import migrate_billing, migrate_stripe, migrate_users_password_hash_nullable
from app.models import Board, BoardColumn, BoardMember, Card, Payment, User  # noqa: F401
from app.schemas.common import ErrorResponse

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.database_url.startswith("sqlite"):
        migrate_users_password_hash_nullable(settings.database_url)
        migrate_billing(settings.database_url)
        migrate_stripe(settings.database_url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="Kanban Backend", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def cors_middleware(request: Request, call_next):
    origin = request.headers.get("origin")
    allowed_origin = origin if is_allowed_origin(origin, settings) else "*"

    if request.method == "OPTIONS" and request.url.path.startswith("/api"):
        return PlainTextResponse(
            status_code=204,
            headers={
                "Access-Control-Allow-Origin": allowed_origin,
                "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
            },
        )

    response = await call_next(request)

    if request.url.path.startswith("/api") or origin:
        response.headers["Access-Control-Allow-Origin"] = allowed_origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"

    return response


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_: Request, exc: StarletteHTTPException):
    if isinstance(exc.detail, str):
        message = exc.detail
    else:
        message = "Request failed"
    return JSONResponse(status_code=exc.status_code, content=ErrorResponse(error=message).model_dump())


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(error="Request body must be valid JSON").model_dump(),
    )


@app.get("/")
async def root() -> PlainTextResponse:
    return PlainTextResponse("Hello World!")


app.include_router(auth.router)
app.include_router(profiles.router)
app.include_router(billing.router)
app.include_router(boards.router)
app.include_router(columns.router)
app.include_router(cards.router)
app.include_router(ai.router)
