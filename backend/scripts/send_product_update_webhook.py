"""Send a signed products/update webhook to the local application.

Shopify signs every webhook with the application secret. This script builds a
payload in the same shape Shopify uses, signs it with SHOPIFY_WEBHOOK_SECRET
and posts it to the running backend, so the webhook handler can be exercised
without exposing a tunnel to the internet.

Usage, with the stack running:
    make webhook
    make webhook ARGUMENTS="--price 19.99"
    make webhook ARGUMENTS="--inventory-policy continue"
    make webhook ARGUMENTS="--break-signature"

Directly, from the backend directory:
    python -m scripts.send_product_update_webhook --price 19.99
"""

import argparse
import base64
import hashlib
import hmac
import json
import sys

import httpx

from application.settings import get_settings

DEFAULT_TARGET_URL = "http://localhost:8000/webhooks/shopify/products-update"
DEFAULT_PRODUCT_ID = "8100000000001"
DEFAULT_VARIANT_ID = "45100000000001"


def build_payload(
    product_id: str,
    variant_id: str,
    price: str,
    inventory_policy: str,
    inventory_quantity: int,
) -> dict[str, object]:
    return {
        "id": int(product_id),
        "title": "Everyday Cotton T-Shirt",
        "status": "active",
        "updated_at": "2026-01-15T09:30:00-05:00",
        "variants": [
            {
                "id": int(variant_id),
                "product_id": int(product_id),
                "title": "Small / Black",
                "sku": "COTTON-TEE-S-BLACK",
                "price": price,
                "inventory_policy": inventory_policy,
                "inventory_quantity": inventory_quantity,
                "updated_at": "2026-01-15T09:30:00-05:00",
            }
        ],
    }


def sign(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Send a signed Shopify products/update webhook.")
    parser.add_argument("--target-url", default=DEFAULT_TARGET_URL)
    parser.add_argument("--product-id", default=DEFAULT_PRODUCT_ID)
    parser.add_argument("--variant-id", default=DEFAULT_VARIANT_ID)
    parser.add_argument("--price", default="21.00")
    parser.add_argument("--inventory-policy", default="deny", choices=["deny", "continue"])
    parser.add_argument("--inventory-quantity", type=int, default=12)
    parser.add_argument("--secret", default=settings.shopify_webhook_secret)
    parser.add_argument(
        "--break-signature",
        action="store_true",
        help="Send a wrong signature, to check that the handler rejects it.",
    )
    arguments = parser.parse_args()

    payload = build_payload(
        product_id=arguments.product_id,
        variant_id=arguments.variant_id,
        price=arguments.price,
        inventory_policy=arguments.inventory_policy,
        inventory_quantity=arguments.inventory_quantity,
    )
    body = json.dumps(payload).encode("utf-8")
    signature = sign(arguments.secret, body)
    if arguments.break_signature:
        signature = sign("a-different-secret", body)

    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Topic": "products/update",
        "X-Shopify-Hmac-Sha256": signature,
        "X-Shopify-Shop-Domain": settings.shopify_store_domain or "development-store.myshopify.com",
        "X-Shopify-Webhook-Id": "00000000-0000-0000-0000-000000000001",
        "X-Shopify-API-Version": settings.shopify_api_version,
    }

    try:
        response = httpx.post(arguments.target_url, content=body, headers=headers, timeout=10.0)
    except httpx.HTTPError as error:
        print(f"Could not reach {arguments.target_url}: {error}")
        return 1

    print(f"Sent products/update to {arguments.target_url}")
    print(f"Response status: {response.status_code}")
    if response.content:
        print(f"Response body: {response.text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
