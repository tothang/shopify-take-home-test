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

    - Catalog unreachable: 502 with a short message for the operator.
    - The details go to the server log.
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

    - Invalid input: 422 (from VariantUpdateRequest).
    - Unknown product or variant: 404.
    - Any other store failure: 502.
    - A field left out of the body is passed as None and stays unchanged.
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
        # - Client error, so not logged.
        # - Also raised for an unknown product.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variant {variant_id} does not exist on product {product_id}.",
        ) from error
    except ShopifyError as error:
        # - Any other store failure, including rejected changes, means "not saved".
        # - Must come after VariantNotFoundError, which is a ShopifyError subclass.
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
