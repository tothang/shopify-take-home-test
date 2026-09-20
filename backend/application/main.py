from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from application.dependencies import close_graphql_clients
from application.routers import authentication, events, health, products, webhooks
from application.settings import get_settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await close_graphql_clients()


def create_application() -> FastAPI:
    settings = get_settings()
    instance = FastAPI(
        title="Shopify Pricing Console",
        version="1.0.0",
        lifespan=lifespan,
    )
    instance.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["*"],
    )
    instance.include_router(health.router)
    instance.include_router(authentication.router)
    instance.include_router(products.router)
    instance.include_router(events.router)
    instance.include_router(webhooks.router)
    return instance


application = create_application()
