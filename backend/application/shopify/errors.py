class ShopifyError(RuntimeError):
    """The Shopify Admin API could not fulfill a request."""


class VariantNotFoundError(ShopifyError):
    """The requested variant does not exist in the store."""


class VariantUpdateRejectedError(ShopifyError):
    """Shopify accepted the request but refused the change.

    Raised when a mutation comes back with entries in userErrors.
    """
