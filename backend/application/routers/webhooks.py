from fastapi import APIRouter, HTTPException, Request, Response, status

from application.dependencies import SettingsDependency

router = APIRouter(prefix="/webhooks/shopify", tags=["webhooks"])


@router.post("/products-update")
async def handle_product_update(request: Request, settings: SettingsDependency) -> Response:
    """Task 3: accept the products/update webhook and feed the event stream.

    Shopify sends the REST shaped payload, so variant fields arrive as
    "price": "24.00" and "inventory_policy": "continue". The application
    models use InventoryPolicy.CONTINUE, so a mapping step is needed.

    Requirements:
      - reject a request whose signature does not verify
      - answer quickly; Shopify retries anything that is slow or fails
      - publish one VariantUpdatedEvent per variant in the payload, using
        event_broker.publish

    backend/scripts/send_product_update_webhook.py sends a correctly signed
    request so you can test this without exposing your machine to the
    internet. Run it with: make webhook
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Task 3: verify the signature and publish the variant updates.",
    )
