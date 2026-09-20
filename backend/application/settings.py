from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# The .env file lives at the repository root. Anchored to this file rather than
# the working directory, so running from backend/ outside Docker still finds it.
# Inside the container the path does not exist, and compose injects the values.
ENVIRONMENT_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """Runtime configuration, loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=ENVIRONMENT_FILE, env_file_encoding="utf-8", extra="ignore")

    shopify_store_domain: str = ""
    shopify_admin_access_token: str = ""
    shopify_api_version: str = "2026-07"
    shopify_webhook_secret: str = "local-development-secret"

    shopify_api_key: str = ""
    shopify_api_secret: str = ""
    shopify_application_url: str = "http://localhost:8000"
    shopify_scopes: str = "read_products,write_products,read_inventory"

    use_mock_shopify: bool = True
    allowed_origins: str = "http://localhost:5173"
    request_timeout_seconds: float = 10.0

    @property
    def allowed_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def installation_redirect_url(self) -> str:
        return f"{self.shopify_application_url.rstrip('/')}/auth/callback"


@lru_cache
def get_settings() -> Settings:
    return Settings()
