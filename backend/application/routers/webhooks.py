import json
import logging
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Request, Response, status

from application.dependencies import SettingsDependency
from application.services.variant_updates import SOURCE_WEBHOOK, broadcast_variant_update
from application.shopify.webhook_payload import variants_from_webhook_payload
from application.shopify.webhook_signature import verify_webhook_signature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/shopify", tags=["webhooks"])

SIGNATURE_HEADER = "X-Shopify-Hmac-Sha256"
SHOP_DOMAIN_HEADER = "X-Shopify-Shop-Domain"


@router.post("/products-update", status_code=status.HTTP_204_NO_CONTENT)
async def handle_product_update(request: Request, settings: SettingsDependency) -> Response:
    """Accept the products/update webhook and feed the event stream.

    - Shopify retries anything slower than about five seconds, so this only
      verifies, maps and publishes (publishing never blocks).
    - Anything slow should move behind a queue.
    - Only a bad signature is rejected (401).
    - Everything else gets 204: a retry would not fix an unreadable payload.
    """
    raw_body = await request.body()
    shop_domain = request.headers.get(SHOP_DOMAIN_HEADER, "")

    if not verify_webhook_signature(
        settings.shopify_webhook_secret,
        raw_body,
        request.headers.get(SIGNATURE_HEADER),
    ):
        # Unverified request, so the shop domain header is only a claim.
        logger.warning(
            "Rejected a webhook whose signature did not verify.",
            extra={"claimed_shop_domain": shop_domain, "body_bytes": len(raw_body)},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The webhook signature did not verify.",
        )

    try:
        # parse_float=Decimal so a numeric price never becomes a float.
        payload = json.loads(raw_body, parse_float=Decimal)
        variants = variants_from_webhook_payload(payload)
    except (ValueError, KeyError, TypeError):
        # - A retry would send the same bytes and fail again.
        # - So accept it and log the failure.
        logger.exception(
            "A signed webhook could not be read.",
            extra={"shop_domain": shop_domain, "body_bytes": len(raw_body)},
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    for variant in variants:
        await broadcast_variant_update(variant, source=SOURCE_WEBHOOK)

    logger.info(
        "Accepted a products/update webhook.",
        extra={"shop_domain": shop_domain, "variant_count": len(variants)},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
