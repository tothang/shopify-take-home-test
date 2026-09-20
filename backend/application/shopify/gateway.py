from decimal import Decimal
from typing import Protocol

from application.schemas import InventoryPolicy, Product, ProductVariant


class ProductGateway(Protocol):
    """Everything the application needs from a product catalog.

    Two implementations exist: InMemoryProductGateway for offline work and
    AdminApiProductGateway for a real Shopify store. Routers depend on this
    protocol, never on a concrete implementation.
    """

    async def list_products(self, limit: int = 25) -> list[Product]:
        """Return up to limit products with their variants."""
        ...

    async def update_variant(
        self,
        product_id: str,
        variant_id: str,
        price: Decimal | None = None,
        inventory_policy: InventoryPolicy | None = None,
    ) -> ProductVariant:
        """Apply the requested changes and return the stored variant.

        Raises VariantNotFoundError when the variant does not exist and
        VariantUpdateRejectedError when the catalog refuses the change.
        """
        ...
