import base64
import hashlib
import hmac


def verify_webhook_signature(secret: str, request_body: bytes, header_value: str | None) -> bool:
    """Return True when the request really came from Shopify.

    Shopify signs the raw request body with the application secret and sends
    the digest base64 encoded in the X-Shopify-Hmac-Sha256 header.

    The body must be the bytes that arrived. Parsing the JSON and serializing
    it again changes the whitespace and the key order, and the digest of that
    will not match.

    A malformed header is a rejection rather than an error: anyone can post to
    this endpoint with any header they like, so bad input is expected traffic.
    """
    # An HMAC keyed with the empty string is something anyone can compute. A
    # backend started without SHOPIFY_WEBHOOK_SECRET must accept nothing, not
    # everything, so this is refused before any digest is made.
    if not secret:
        return False

    if not header_value:
        return False

    try:
        provided_digest = base64.b64decode(header_value, validate=True)
    except ValueError:
        # Not base64, or not ASCII. binascii.Error is a subclass of ValueError.
        return False

    expected_digest = hmac.new(secret.encode("utf-8"), request_body, hashlib.sha256).digest()

    # Constant time. A plain == would leak how much of the digest was correct
    # through how long the comparison took, one byte at a time.
    return hmac.compare_digest(expected_digest, provided_digest)
