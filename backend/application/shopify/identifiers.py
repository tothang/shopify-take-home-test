def to_global_identifier(resource: str, numeric_identifier: str) -> str:
    """Turn "8100000000001" into "gid://shopify/Product/8100000000001"."""
    if numeric_identifier.startswith("gid://"):
        return numeric_identifier
    return f"gid://shopify/{resource}/{numeric_identifier}"


def to_numeric_identifier(global_identifier: str) -> str:
    """Turn "gid://shopify/Product/8100000000001" into "8100000000001"."""
    return global_identifier.rsplit("/", maxsplit=1)[-1]
