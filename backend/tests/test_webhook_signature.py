"""Contract tests for task 3. They fail until the signature check is written."""

from application.shopify.webhook_signature import verify_webhook_signature

SECRET = "test-webhook-secret"
BODY = b'{"id":8100000000001,"variants":[{"id":45100000000001,"price":"19.99"}]}'
VALID_SIGNATURE = "l+l9BZgzB2X+MFUAbDKx/6DSRpYy3t1k2i6kux299Q0="


def test_a_signature_produced_by_shopify_is_accepted() -> None:
    assert verify_webhook_signature(SECRET, BODY, VALID_SIGNATURE) is True


def test_a_modified_body_is_rejected() -> None:
    tampered = BODY.replace(b"19.99", b"00.01")

    assert verify_webhook_signature(SECRET, tampered, VALID_SIGNATURE) is False


def test_another_secret_is_rejected() -> None:
    assert verify_webhook_signature("another-secret", BODY, VALID_SIGNATURE) is False


def test_a_missing_header_is_rejected() -> None:
    assert verify_webhook_signature(SECRET, BODY, None) is False


def test_a_header_that_is_not_valid_base64_is_rejected() -> None:
    assert verify_webhook_signature(SECRET, BODY, "not base64 at all") is False
