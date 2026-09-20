from fastapi import APIRouter

from application.dependencies import SettingsDependency
from application.services.event_broker import event_broker
from application.services.shop_token_store import shop_token_store

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def read_health(settings: SettingsDependency) -> dict[str, object]:
    return {
        "status": "ok",
        "using_mock_shopify": settings.use_mock_shopify,
        "shopify_api_version": settings.shopify_api_version,
        "event_stream_subscribers": event_broker.subscriber_count,
        "installed_shops": shop_token_store.installed_shops,
    }
