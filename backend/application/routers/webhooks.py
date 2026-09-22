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

    Shopify waits about five seconds and retries anything slower or failed, so
    this does the least it can: verify, map, publish. Publishing is a
    put_nowait onto the queue of each connected browser and never blocks. The
    moment this path grows something slow, a database write or a call back to
    Shopify, it belongs behind a queue instead.

    Anything other than a bad signature answers 204. A retry cannot improve a
    payload we could not read, and a webhook Shopify keeps redelivering is
    worse than one dropped loudly into the log.
    """
    raw_body = await request.body()
    shop_domain = request.headers.get(SHOP_DOMAIN_HEADER, "")

    if not verify_webhook_signature(
        settings.shopify_webhook_secret,
        raw_body,
        request.headers.get(SIGNATURE_HEADER),
    ):
        # The shop domain is only a header, and this request has just failed to
        # prove it came from Shopify. It is logged as a claim, not as a fact.
        logger.warning(
            "Rejected a webhook whose signature did not verify.",
            extra={"claimed_shop_domain": shop_domain, "body_bytes": len(raw_body)},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The webhook signature did not verify.",
        )

    try:
        # parse_float keeps a price that arrives as a JSON number out of a
        # float. Shopify sends money as a string, but this costs nothing.
        payload = json.loads(raw_body, parse_float=Decimal)
        variants = variants_from_webhook_payload(payload)
    except (ValueError, KeyError, TypeError):
        # The signature verified, so Shopify sent exactly these bytes. A retry
        # would send them again and fail the same way, so the request is
        # accepted and the failure is left in the log, where someone can act on it.
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
