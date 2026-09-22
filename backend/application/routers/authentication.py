import hmac
import logging
import secrets

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse

from application.dependencies import SettingsDependency
from application.services.shop_token_store import shop_token_store
from application.settings import Settings
from application.shopify.errors import ShopifyError
from application.shopify.graphql_client import ShopifyGraphQLClient
from application.shopify.oauth import (
    build_authorization_url,
    exchange_code_for_access_token,
    is_valid_shop_domain,
    verify_callback_signature,
)
from application.shopify.webhook_subscription import register_products_update_webhook

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])

# The state travels in a cookie on the merchant's own browser, not in a table
# on the server. See start_installation for why.
STATE_COOKIE_NAME = "shopify_installation_state"
STATE_COOKIE_PATH = "/auth"
STATE_LIFETIME_SECONDS = 600


@router.get("/install")
async def start_installation(shop: str, settings: SettingsDependency) -> Response:
    """Send the merchant to Shopify to approve the access scopes.

    Called as /auth/install?shop=their-store.myshopify.com, by anyone. The
    shop domain is checked before anything else touches it, because it becomes
    the host of a URL this application later posts its client secret to.

    Where the state lives. It is a random value set as a cookie on the browser
    that started the installation, and the callback only proceeds when the
    state Shopify hands back matches that cookie. A table on the server would
    prove that this application issued the state, but not that the browser
    returning with it is the one it was issued to. That second part is what
    stops somebody from starting an installation themselves and then tricking
    a merchant into finishing it. The cookie also survives a restart and works
    across several backend processes, which an in-memory table would not.

    SameSite=Lax rather than Strict: the merchant comes back through a top
    level redirect from Shopify, which is a cross-site navigation, and a
    Strict cookie is not sent on those.
    """
    shop_domain = shop.strip().lower()
    if not is_valid_shop_domain(shop_domain):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That is not a Shopify shop domain. Use the form your-store.myshopify.com.",
        )

    if not settings.shopify_api_key or not settings.shopify_api_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The application has no Shopify credentials. Set SHOPIFY_API_KEY and SHOPIFY_API_SECRET.",
        )

    state = secrets.token_urlsafe(32)
    response = RedirectResponse(
        build_authorization_url(
            shop_domain=shop_domain,
            api_key=settings.shopify_api_key,
            scopes=settings.shopify_scopes,
            redirect_url=settings.installation_redirect_url,
            state=state,
        ),
        status_code=status.HTTP_302_FOUND,
    )
    response.set_cookie(
        STATE_COOKIE_NAME,
        state,
        max_age=STATE_LIFETIME_SECONDS,
        path=STATE_COOKIE_PATH,
        httponly=True,
        samesite="lax",
        secure=settings.shopify_application_url.startswith("https://"),
    )
    return response


@router.get("/callback")
async def complete_installation(request: Request, settings: SettingsDependency) -> Response:
    """Finish the installation and store the access token.

    Every check comes before the token exchange, and each one that fails ends
    the request. The order is cheapest first, and the signature leads because
    until it passes, nothing else in the URL is known to come from Shopify.
    """
    parameters = dict(request.query_params)

    # A repeated parameter would be signed as one value and read as another.
    if len(request.query_params.multi_items()) != len(parameters):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A parameter appears more than once.")

    if not verify_callback_signature(settings.shopify_api_secret, parameters):
        logger.warning(
            "Rejected an installation callback whose signature did not verify.",
            extra={"claimed_shop_domain": parameters.get("shop", "")},
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "The callback signature did not verify.")

    shop_domain = parameters.get("shop", "")
    code = parameters.get("code", "")
    if not is_valid_shop_domain(shop_domain) or not code:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The callback is missing the shop or the code.")

    expected_state = request.cookies.get(STATE_COOKIE_NAME, "")
    returned_state = parameters.get("state", "")
    if not expected_state or not hmac.compare_digest(expected_state, returned_state):
        logger.warning(
            "Rejected an installation callback whose state did not match.",
            extra={"shop_domain": shop_domain, "had_state_cookie": bool(expected_state)},
        )
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This installation was not started from this browser, or it took too long. Start it again.",
        )

    try:
        access_token = await exchange_code_for_access_token(
            shop_domain=shop_domain,
            api_key=settings.shopify_api_key,
            api_secret=settings.shopify_api_secret,
            code=code,
            timeout_seconds=settings.request_timeout_seconds,
        )
    except ShopifyError as error:
        logger.exception("The access token exchange failed.", extra={"shop_domain": shop_domain})
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Shopify did not issue an access token. Start the installation again.",
        ) from error

    shop_token_store.save(shop_domain, access_token)
    logger.info("Installed into a shop.", extra={"shop_domain": shop_domain})

    await _register_webhook(shop_domain, access_token, settings)

    response = RedirectResponse(settings.frontend_url, status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(STATE_COOKIE_NAME, path=STATE_COOKIE_PATH)
    return response


async def _register_webhook(shop_domain: str, access_token: str, settings: Settings) -> None:
    """Subscribe to products/update, without letting a failure undo the install.

    Shopify refuses an address it cannot reach, and http://localhost is one.
    The token is already saved and the console works without the webhook; it
    only stops hearing about edits made elsewhere. So a failure is logged and
    the merchant carries on.
    """
    client = ShopifyGraphQLClient(
        store_domain=shop_domain,
        access_token=access_token,
        api_version=settings.shopify_api_version,
        timeout_seconds=settings.request_timeout_seconds,
    )
    try:
        await register_products_update_webhook(client, settings.products_update_webhook_url)
    except ShopifyError:
        logger.warning(
            "Could not register the products/update webhook. The installation continues without it.",
            exc_info=True,
            extra={"shop_domain": shop_domain, "uri": settings.products_update_webhook_url},
        )
    finally:
        await client.aclose()
