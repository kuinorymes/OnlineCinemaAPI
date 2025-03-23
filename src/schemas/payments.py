from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from decimal import Decimal

from database.models.payments import PaymentStatusEnum


class PaymentCreate(BaseModel):
    order_id: int

    model_config = {
        "from_attributes": True
    }


class PaymentItemResponse(BaseModel):
    id: int
    order_item_id: int
    price_at_payment: Decimal

    model_config = {
        "from_attributes": True
    }


class PaymentResponse(BaseModel):
    id: int
    order_id: int
    amount: Decimal
    status: PaymentStatusEnum
    created_at: datetime
    recommendation: Optional[str] = None

    model_config = {
        "from_attributes": True
    }


class StripePaymentSessionResponse(BaseModel):
    payment_id: int
    session_id: str
    session_url: str
    status: str = "pending"

    model_config = {
        "from_attributes": True
    }
