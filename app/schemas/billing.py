from pydantic import BaseModel, Field


class PlanOut(BaseModel):
    id: str
    name: str
    priceUsd: int
    description: str


class SubscriptionOut(BaseModel):
    planId: str
    planName: str
    priceUsd: int


class SubscribeRequest(BaseModel):
    planId: str = Field(min_length=1, max_length=20)


class CheckoutRequest(BaseModel):
    planId: str = Field(min_length=1, max_length=20)


class CheckoutOut(BaseModel):
    checkoutUrl: str


class PaymentOut(BaseModel):
    id: str
    planId: str
    planName: str
    amountCents: int
    status: str
    createdAt: str

    model_config = {"from_attributes": True}
