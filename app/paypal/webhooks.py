import logging
from typing import Dict, Any, Optional
from fastapi import Request
from app.config import settings
from app.paypal.client import paypal_client

logger = logging.getLogger("merchant_shield.webhooks")


async def verify_webhook_signature(
    request: Request, body_bytes: bytes, webhook_id: str
) -> bool:
    """
    Verifies incoming webhook signature using PayPal's /v1/notifications/verify-webhook-signature API.
    Prevents forged HTTP POST requests from unauthorized callers.
    """
    headers = request.headers
    transmission_id = headers.get("paypal-transmission-id")
    transmission_time = headers.get("paypal-transmission-time")
    cert_url = headers.get("paypal-cert-url")
    auth_algo = headers.get("paypal-auth-algo")
    transmission_sig = headers.get("paypal-transmission-sig")

    if not all(
        [transmission_id, transmission_time, cert_url, auth_algo, transmission_sig]
    ):
        logger.warning("Missing required PayPal signature headers.")
        return False

    import json

    try:
        event_body = json.loads(body_bytes.decode("utf-8"))
    except Exception:
        return False

    payload = {
        "transmission_id": transmission_id,
        "transmission_time": transmission_time,
        "cert_url": cert_url,
        "auth_algo": auth_algo,
        "transmission_sig": transmission_sig,
        "webhook_id": webhook_id,
        "webhook_event": event_body,
    }

    try:
        res = await paypal_client.request(
            method="POST",
            endpoint="/v1/notifications/verify-webhook-signature",
            json=payload,
        )
        status = res.get("verification_status", "").upper()
        return status == "SUCCESS"
    except Exception as e:
        logger.error(f"Webhook signature verification request failed: {e}")
        return False
