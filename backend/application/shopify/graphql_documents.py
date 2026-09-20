"""GraphQL documents used against the Shopify Admin API.

Task 5 asks you to fill these in. The application models need, for every
variant: identifier, product identifier, title, stock keeping unit, price,
currency code, available stock, inventory policy and the last update time.

Identifiers in the application layer are numeric strings, for example
"8100000000001". Shopify works with global identifiers, for example
"gid://shopify/Product/8100000000001". Use to_global_identifier and
to_numeric_identifier in identifiers.py at the boundary.
"""

PRODUCTS_QUERY = ""

VARIANT_UPDATE_MUTATION = ""
