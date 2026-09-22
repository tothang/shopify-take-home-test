import logging

from fastapi import APIRouter, HTTPException, status

from application.dependencies import ProductGatewayDependency
from application.schemas import Product, ProductVariant, VariantUpdateRequest
from application.services.variant_updates import apply_variant_change
from application.shopify.errors import ShopifyError, VariantNotFoundError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=list[Product])
async def list_products(gateway: ProductGatewayDependency) -> list[Product]:
    """Return the catalog.

    When the catalog is unreachable the browser gets a 502 with a short
    message it can show to the operator. The details stay in the server log,
    because a stack trace in the browser console is not an answer.
    """
    try:
        return await gateway.list_products()
    except ShopifyError as error:
        logger.exception(
            "Listing products failed.",
            extra={"error_type": type(error).__name__, "gateway": type(gateway).__name__},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The catalog is unavailable right now. Try again in a moment.",
        ) from error


@router.patch("/{product_id}/variants/{variant_id}", response_model=ProductVariant)
async def update_variant(
    product_id: str,
    variant_id: str,
    payload: VariantUpdateRequest,
    gateway: ProductGatewayDependency,
) -> ProductVariant:
    """Change the price, the inventory policy, or both.

    The body has already been through VariantUpdateRequest, which rejects an
    empty body, a price that is not above zero, more than two decimal places
    and an unknown policy, all as 422. What is left is the catalog's answer: an
    identifier that does not exist is the caller's mistake and a 404, and
    anything else is the store failing, which is a 502.

    A field left out of the body stays as it is, because the gateway is given
    None for it rather than the current value.
    """
    try:
        return await apply_variant_change(
            gateway,
            product_id=product_id,
            variant_id=variant_id,
            price=payload.price,
            inventory_policy=payload.inventory_policy,
        )
    except VariantNotFoundError as error:
        # A client error, so it is not logged as a fault of ours. Both
        # identifiers came from the caller's own URL, so echoing them leaks
        # nothing they did not already send. The gateway raises this for an
        # unknown product as well, because there is no separate error type.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variant {variant_id} does not exist on product {product_id}.",
        ) from error
    except ShopifyError as error:
        # Everything else the store can do to us, including a mutation that
        # came back with userErrors as VariantUpdateRejectedError, is one thing
        # to the operator: the change was not saved. The order of these two
        # clauses matters, because VariantNotFoundError is a subclass of
        # ShopifyError and would otherwise be answered with a 502.
        logger.exception(
            "Updating a variant failed.",
            extra={
                "gateway": type(gateway).__name__,
                "product_id": product_id,
                "variant_id": variant_id,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The change could not be saved. Try again in a moment.",
        ) from error
