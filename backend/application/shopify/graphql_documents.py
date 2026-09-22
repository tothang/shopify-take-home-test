"""GraphQL documents used against the Shopify Admin API.

Task 5 asks you to fill these in. The application models need, for every
variant: identifier, product identifier, title, stock keeping unit, price,
currency code, available stock, inventory policy and the last update time.

Identifiers in the application layer are numeric strings, for example
"8100000000001". Shopify works with global identifiers, for example
"gid://shopify/Product/8100000000001". Use to_global_identifier and
to_numeric_identifier in identifiers.py at the boundary.
"""

# Everything ProductVariant needs, in one place, so the read and the write
# cannot drift apart. The currency is not here: a variant's price is always in
# the shop currency, which only the shop knows.
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

# Shopify refuses a query whose calculated cost is above 1000. A connection
# costs about 2 plus first times its children, so 25 products with 30 variants
# each comes to roughly 2 + 25 * (3 + 30) = 827. Asking for 100 variants would
# be refused outright. hasNextPage says when a product has more than we read.
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

# productVariantsBulkUpdate is the current way to change a variant; the older
# productVariantUpdate is gone. One variant, both fields, one request. A field
# the operator did not change is left out of the input, so Shopify leaves it.
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

# Registered once per shop at installation. The topic is PRODUCTS_UPDATE, which
# is the one the webhook route handles. The field is uri: callbackUrl is what
# older versions of the Admin API called it.
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
