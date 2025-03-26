import os
import logging
import stripe

from dotenv import load_dotenv
from fastapi import HTTPException
from typing import Dict, Optional


load_dotenv()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

logger = logging.getLogger(__name__)


class StripeService:
    def __init__(self, api_key: str, webhook_secret: str):
        stripe.api_key = api_key
        self.webhook_secret = webhook_secret

    async def create_checkout_session(
        self,
        amount: float,
        order_id: int,
        user_id: int,
        success_url: str,
        cancel_url: str,
        description: str,
    ) -> Dict:
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[
                    {
                        "price_data": {
                            "currency": "usd",
                            "product_data": {
                                "name": description,
                            },
                            "unit_amount": int(amount * 100),
                        },
                        "quantity": 1,
                    }
                ],
                mode="payment",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={"user_id": str(user_id), "order_id": str(order_id)},
            )
            return {
                "id": session.id,
                "url": session.url,
                "customer_email": (
                    session.customer_details.email if session.customer_details else None
                ),
            }
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def verify_stripe_payment(self, session_id: str) -> bool:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            return session.payment_status == "paid"
        except stripe.error.StripeError as e:
            logger.error(f"Stripe verification failed: {str(e)}")
            return False

    async def retrieve_session(self, session_id: str) -> Optional[Dict]:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            return {
                "id": session.id,
                "payment_status": session.payment_status,
                "customer_email": (
                    session.customer_details.email if session.customer_details else None
                ),
                "metadata": session.metadata,
            }
        except stripe.error.StripeError as e:
            logger.error(f"Failed to retrieve Stripe session: {str(e)}")
            return None

    async def construct_webhook_event(self, payload: bytes, sig_header: str):
        try:
            return stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except stripe.error.SignatureVerificationError as e:
            raise HTTPException(status_code=400, detail=str(e))
