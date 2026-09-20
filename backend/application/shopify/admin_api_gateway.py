from decimal import Decimal

from application.schemas import InventoryPolicy, Product, ProductVariant
from application.shopify.graphql_client import ShopifyGraphQLClient


class AdminApiProductGateway:
    """Reads and writes the catalog of a real Shopify store.

    Task 5: implement both methods against the Shopify Admin GraphQL API,
    using the documents in graphql_documents.py.

    Points to get right:
      - map the GraphQL response onto the Product and ProductVariant models
      - convert between numeric identifiers and global identifiers
      - treat a mutation that returns userErrors as a failure, not a success
      - raise VariantNotFoundError when the variant is unknown to the store
      - never send money values through a floating point number
    """

    def __init__(self, client: ShopifyGraphQLClient) -> None:
        self._client = client

    async def list_products(self, limit: int = 25) -> list[Product]:
        raise NotImplementedError("Task 5: read products and variants from the Shopify Admin API.")

    async def update_variant(
        self,
        product_id: str,
        variant_id: str,
        price: Decimal | None = None,
        inventory_policy: InventoryPolicy | None = None,
    ) -> ProductVariant:
        raise NotImplementedError("Task 5: update price and inventory policy through the Shopify Admin API.")
