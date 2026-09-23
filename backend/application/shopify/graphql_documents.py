"""GraphQL documents used against the Shopify Admin API.

Task 5 asks you to fill these in. The application models need, for every
variant: identifier, product identifier, title, stock keeping unit, price,
currency code, available stock, inventory policy and the last update time.

Identifiers in the application layer are numeric strings, for example
"8100000000001". Shopify works with global identifiers, for example
"gid://shopify/Product/8100000000001". Use to_global_identifier and
to_numeric_identifier in identifiers.py at the boundary.
"""

# Variant fields:
# - shared by the read and the write so they stay in sync
# - no currency here; it comes from the shop
VARIANT_FIELDS = """
fragment VariantFields on ProductVariant {
  id
  title
  sku
  price
  inventoryQuantity
  inventoryPolicy
  updatedAt
  product {
    id
  }
}
"""

# Keeps the query under Shopify's cost limit of 1000:
# - 25 products * 30 variants costs about 2 + 25 * (3 + 30) = 827
# - 100 variants would be refused
# - hasNextPage tells us when a product has more
VARIANTS_PER_PRODUCT = 30

PRODUCTS_QUERY = (
    """
query Products($first: Int!, $variantsPerProduct: Int!) {
  shop {
    currencyCode
  }
  products(first: $first, sortKey: TITLE) {
    nodes {
      id
      title
      status
      variants(first: $variantsPerProduct) {
        nodes {
          ...VariantFields
        }
        pageInfo {
          hasNextPage
        }
      }
    }
  }
}
"""
    + VARIANT_FIELDS
)

# - productVariantsBulkUpdate replaces the removed productVariantUpdate.
# - Fields left out of the input are not changed.
VARIANT_UPDATE_MUTATION = (
    """
mutation UpdateVariant($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
    productVariants {
      ...VariantFields
    }
    userErrors {
      field
      message
      code
    }
  }
}
"""
    + VARIANT_FIELDS
)

SHOP_CURRENCY_QUERY = """
query ShopCurrency {
  shop {
    currencyCode
  }
}
"""

# - Registered once per shop at install.
# - `uri` was called callbackUrl in older API versions.
WEBHOOK_SUBSCRIPTION_CREATE_MUTATION = """
mutation RegisterWebhook($topic: WebhookSubscriptionTopic!, $webhookSubscription: WebhookSubscriptionInput!) {
  webhookSubscriptionCreate(topic: $topic, webhookSubscription: $webhookSubscription) {
    webhookSubscription {
      id
    }
    userErrors {
      field
      message
    }
  }
}
"""
