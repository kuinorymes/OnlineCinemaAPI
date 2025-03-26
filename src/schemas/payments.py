from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from database.models.payments import PaymentStatusEnum


class PaymentCreateRequest(BaseModel):
    order_id: int


class PaymentItemResponse(BaseModel):
    id: int
    order_item_id: int
    price_at_payment: float

    model_config = {"from_attributes": True}


class PaymentResponse(BaseModel):
    id: int
    user_id: int
    order_id: int
    created_at: datetime
    status: PaymentStatusEnum
    amount: float
    external_payment_id: Optional[str] = None
    payment_url: Optional[str] = None

    model_config = {
        "json_encoders": {datetime: lambda v: v.isoformat()},
        "from_attributes": True,
    }


class PaymentDetailResponse(PaymentResponse):
    payment_items: List[PaymentItemResponse]


class PaymentListResponse(BaseModel):
    payments: List[PaymentResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class PaymentSuccessResponse(BaseModel):
    status: str
    message: str
    order_id: int
    payment_id: int
    amount: float
    paid_at: str


class PaymentCancelResponse(BaseModel):
    status: str
    message: str
    order_id: int
    payment_id: int
    canceled_at: str
