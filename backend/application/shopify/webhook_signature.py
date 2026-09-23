import base64
import hashlib
import hmac


def verify_webhook_signature(secret: str, request_body: bytes, header_value: str | None) -> bool:
    """Return True when the request really came from Shopify.

    - Shopify signs the raw body with the app secret.
    - The digest is base64 in X-Shopify-Hmac-Sha256.
    - Use the raw bytes: re-serialized JSON will not match.
    - A malformed header returns False rather than raising.
    """
    # Anyone can compute an HMAC with an empty key, so reject everything.
    if not secret:
        return False

    if not header_value:
        return False

    try:
        provided_digest = base64.b64decode(header_value, validate=True)
    except ValueError:
        # Not valid base64 (binascii.Error is a ValueError).
        return False

    expected_digest = hmac.new(secret.encode("utf-8"), request_body, hashlib.sha256).digest()

    # Constant-time comparison to avoid timing attacks.
    return hmac.compare_digest(expected_digest, provided_digest)
