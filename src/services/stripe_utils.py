import stripe
from datetime import datetime

stripe.api_key = "sk_test_51QxBPLKX7EO9LjLpMK58n2sEjFFAqE11RuyUCFgTIvLSS7uH4Ho4jLmeNmL224hallbOWXxih3v7XKIbGkp4TMhw00oFPR3ImN"

def create_checkout_session(order_id: int, total_amount: float, user_id: int) -> str:
    current_time = datetime.now().time()
    time_str = current_time.strftime("%H%M%S")
    idempotency_key = f"order_{order_id}_{time_str}"

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": "Your Order",
                        },
                        "unit_amount": int(total_amount * 100),
                    },
                    "quantity": 1,
                },
            ],
            mode="payment",
            success_url=f"http://localhost:8000/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"http://localhost:8000/cancel",
            idempotency_key=idempotency_key
        )
        return checkout_session.url
    except stripe.error.StripeError as e:
        raise Exception(f"Error when creating a Stripe session: {str(e)}")