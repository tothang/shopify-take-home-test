from fastapi import APIRouter, HTTPException, status

from application.dependencies import ProductGatewayDependency
from application.schemas import Product, ProductVariant, VariantUpdateRequest

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=list[Product])
async def list_products(gateway: ProductGatewayDependency) -> list[Product]:
    """Task 1: return the catalog.

    The contract is described in the README. Decide what
    should happen when the catalog is unreachable, and make sure the failure
    reaches the browser as something it can act on.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Task 1: list products through the product gateway.",
    )


@router.patch("/{product_id}/variants/{variant_id}", response_model=ProductVariant)
async def update_variant(
    product_id: str,
    variant_id: str,
    payload: VariantUpdateRequest,
    gateway: ProductGatewayDependency,
) -> ProductVariant:
    """Task 2: change the price, the inventory policy, or both.

    The contract is described in the README. An unknown
    variant is a client error, not a server error.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Task 2: update the variant through the product gateway.",
    )
