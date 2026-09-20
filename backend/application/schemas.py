from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class InventoryPolicy(StrEnum):
    """Mirrors the Shopify ProductVariantInventoryPolicy enumeration.

    DENY stops the storefront from selling once available stock reaches zero.
    CONTINUE keeps the variant purchasable, which is what merchants call
    "continue selling when out of stock".
    """

    DENY = "DENY"
    CONTINUE = "CONTINUE"


class ProductVariant(BaseModel):
    """A single purchasable variant.

    Prices are decimals and are serialized as strings, the same way Shopify
    represents money. Do not convert them to floating point numbers.
    """

    id: str
    product_id: str
    title: str
    sku: str | None = None
    price: Decimal
    currency_code: str
    inventory_quantity: int
    inventory_policy: InventoryPolicy
    updated_at: datetime


class Product(BaseModel):
    id: str
    title: str
    status: str
    variants: list[ProductVariant]


class VariantUpdateRequest(BaseModel):
    """Body of the variant update endpoint. At least one field is required."""

    price: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    inventory_policy: InventoryPolicy | None = None

    @model_validator(mode="after")
    def require_at_least_one_change(self) -> "VariantUpdateRequest":
        if self.price is None and self.inventory_policy is None:
            raise ValueError("Provide at least one of price or inventory_policy.")
        return self


class VariantUpdatedEvent(BaseModel):
    """Payload pushed to connected browsers over the event stream."""

    source: str
    variant: ProductVariant
