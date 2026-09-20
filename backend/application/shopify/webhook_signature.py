def verify_webhook_signature(secret: str, request_body: bytes, header_value: str | None) -> bool:
    """Return True when the request really came from Shopify.

    Task 3: implement this. Shopify signs the raw request body with the
    application secret and sends the result in the X-Shopify-Hmac-Sha256
    header. Use the raw bytes of the body, not a parsed and re-serialized
    copy of it, and compare the two values in constant time.

    The provided tests in tests/test_webhook_signature.py define the expected
    behavior, including what happens when the header is missing or malformed.
    """
    raise NotImplementedError("Task 3: verify the Shopify webhook signature.")
