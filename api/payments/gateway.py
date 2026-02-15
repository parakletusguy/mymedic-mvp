"""
Payments Domain — Payment Gateway Client.

Abstracts communication with Paystack (primary) and provides a
mock mode for test environments. Flutterwave can be added as a
second provider by implementing the same interface.

SECURITY:
  - Secret key is read from settings, NEVER logged.
  - Webhook signatures are verified via HMAC-SHA512.
  - Raw card data is NEVER sent through our servers (hosted checkout).
"""

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone

import httpx

from api.core.config import settings


class PaystackClient:
    """
    Paystack API v1 client.

    In debug/test mode, all calls are mocked locally so you can
    develop without a real Paystack account.
    """

    BASE_URL = "https://api.paystack.co"

    def __init__(self) -> None:
        self.secret_key = settings.paystack_secret_key
        self.is_mock = settings.debug or self.secret_key == "CHANGE_ME"

    # ── Headers ────────────────────────────────────────────────

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

    # ── Initialize Transaction ─────────────────────────────────

    async def initialize_transaction(
        self,
        email: str,
        amount_kobo: int,
        reference: str,
        callback_url: str,
        metadata: dict | None = None,
    ) -> dict:
        """
        Initialize a Paystack transaction.

        Args:
            email: Customer email.
            amount_kobo: Amount in kobo (₦100 = 10000 kobo).
            reference: Unique transaction reference.
            callback_url: URL Paystack redirects to after payment.
            metadata: Optional metadata dict attached to the transaction.

        Returns:
            Dict with 'authorization_url', 'access_code', 'reference'.
        """
        if self.is_mock:
            return self._mock_initialize(reference, callback_url)

        payload = {
            "email": email,
            "amount": amount_kobo,
            "reference": reference,
            "callback_url": callback_url,
        }
        if metadata:
            payload["metadata"] = metadata

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/transaction/initialize",
                headers=self._headers(),
                json=payload,
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()

        if not data.get("status"):
            raise Exception(f"Paystack init failed: {data.get('message')}")

        return data["data"]

    # ── Verify Transaction ─────────────────────────────────────

    async def verify_transaction(self, reference: str) -> dict:
        """
        Verify a transaction by reference.

        Returns the full transaction data from Paystack.
        """
        if self.is_mock:
            return self._mock_verify(reference)

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/transaction/verify/{reference}",
                headers=self._headers(),
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()

        if not data.get("status"):
            raise Exception(f"Paystack verify failed: {data.get('message')}")

        return data["data"]

    # ── Webhook Signature Verification ─────────────────────────

    def verify_webhook_signature(self, body: bytes, signature: str) -> bool:
        """
        Verify Paystack webhook HMAC-SHA512 signature.

        Paystack signs the raw request body with your secret key.
        This MUST be verified before processing any webhook event.
        """
        if self.is_mock:
            return True  # Accept all in test mode

        expected = hmac.new(
            self.secret_key.encode("utf-8"),
            body,
            hashlib.sha512,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    # ── Mock Responses (Test Mode) ─────────────────────────────

    @staticmethod
    def _mock_initialize(reference: str, callback_url: str) -> dict:
        """Simulate a Paystack initialize response."""
        return {
            "authorization_url": f"{callback_url}?trxref={reference}",
            "access_code": f"mock_access_{uuid.uuid4().hex[:12]}",
            "reference": reference,
        }

    @staticmethod
    def _mock_verify(reference: str) -> dict:
        """Simulate a successful Paystack verification."""
        return {
            "status": "success",
            "reference": reference,
            "amount": 0,  # Will be filled from our DB
            "currency": "NGN",
            "paid_at": datetime.now(timezone.utc).isoformat(),
            "channel": "card",
            "gateway_response": "Successful (MOCK)",
        }


# Singleton
paystack_client = PaystackClient()
