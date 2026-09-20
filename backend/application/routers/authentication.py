from fastapi import APIRouter, HTTPException, Request, Response, status

from application.dependencies import SettingsDependency

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get("/install")
async def start_installation(shop: str, settings: SettingsDependency) -> Response:
    """Task 4: send the merchant to Shopify to approve the access scopes.

    Called as /auth/install?shop=their-store.myshopify.com, by anyone. Reject a
    shop domain that is not a Shopify one before doing anything else with it.

    Carry a state value across to the callback and check it when the merchant
    comes back. Say in your notes where you kept it and why.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Task 4: redirect the merchant to the Shopify authorization screen.",
    )


@router.get("/callback")
async def complete_installation(request: Request, settings: SettingsDependency) -> Response:
    """Task 4: finish the installation and store the access token.

    Shopify sends the merchant back here with a code and a signature. Verify
    the request, exchange the code, save the token in shop_token_store, and
    register the products/update webhook subscription. Then send the merchant
    somewhere that is not a blank page.

    Shopify will not accept a callback address it cannot reach, so the
    subscription call does not succeed while the application URL points at
    localhost. Its failure must not break the installation.

    A request that fails verification must not reach the token exchange.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Task 4: verify the callback, exchange the code and store the token.",
    )
