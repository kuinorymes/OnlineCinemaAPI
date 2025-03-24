from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from database.models.payments import PaymentStatusEnum


class PaymentItemCreate(BaseModel):
    order_item_id: int
    price_at_payment: float

    model_config = {
        "from_attributes": True
    }


class PaymentCreate(BaseModel):
    order_id: int
    amount: float
    payment_items: List[PaymentItemCreate]
    payment_method_id: str

    model_config = {
        "from_attributes": True
    }


class PaymentResponse(BaseModel):
    id: int
    user_id: int
    order_id: int
    created_at: datetime
    status: PaymentStatusEnum
    amount: float
    external_payment_id: Optional[str] = None

    model_config = {
        "from_attributes": True
    }


class PaymentItemResponse(BaseModel):
    id: int
    payment_id: int
    order_item_id: int
    price_at_payment: float

    model_config = {
        "from_attributes": True
    }


class PaymentHistoryResponse(BaseModel):
    payment: PaymentResponse
    items: List[PaymentItemResponse]

    model_config = {
        "from_attributes": True
    }


class PaymentStatusUpdate(BaseModel):
    status: PaymentStatusEnum
    external_payment_id: Optional[str] = None

    model_config = {
        "from_attributes": True
    }
