from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

from database.models.payments import PaymentStatusEnum


class PaymentItemCreate(BaseModel):
    order_item_id: int = Field(..., gt=0, description="Order item ID")
    price_at_payment: float = Field(
        ..., gt=0, description="Price at the time of payment"
    )

    @field_validator("price_at_payment")
    @classmethod
    def round_price(cls, v):
        return round(v, 2)


class PaymentCreate(BaseModel):
    order_id: int = Field(..., gt=0, description="Order ID")
    payment_items: List[PaymentItemCreate] = Field(
        ..., min_length=1, description="List of paid items"
    )
    payment_method_id: str = Field(
        ..., min_length=1, description="Payment method ID in Stripe"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "order_id": 1,
                "payment_items": [
                    {"order_item_id": 1, "price_at_payment": 10.50},
                    {"order_item_id": 2, "price_at_payment": 15.75},
                ],
                "payment_method_id": "pm_123456789",
            }
        }
    }


class PaymentResponse(BaseModel):
    id: int
    user_id: int
    order_id: int
    created_at: datetime
    status: PaymentStatusEnum
    amount: Decimal
    external_payment_id: Optional[str] = None
    items: List["PaymentItemResponse"]

    model_config = {
        "json_encoders": {
            Decimal: lambda v: float(round(v, 2)),
            datetime: lambda v: v.isoformat(),
        },
        "from_attributes": True,
    }


class PaymentItemResponse(BaseModel):
    id: int
    payment_id: int
    order_item_id: int
    price_at_payment: Decimal

    model_config = {
        "json_encoders": {Decimal: lambda v: float(round(v, 2))},
        "from_attributes": True,
    }


class PaymentHistoryResponse(BaseModel):
    payment: PaymentResponse
    items: List[PaymentItemResponse]

    model_config = {"from_attributes": True}


class PaymentStatusUpdate(BaseModel):
    status: PaymentStatusEnum
    external_payment_id: Optional[str] = Field(
        None, min_length=1, description="Payment ID in external system"
    )

    model_config = {
        "json_schema_extra": {
            "example": {"status": "Successful", "external_payment_id": "pi_123456789"}
        }
    }
