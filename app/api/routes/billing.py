from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.billing import (
    CheckoutConfirmRequest,
    CheckoutOut,
    CheckoutRequest,
    PaymentOut,
    PlanOut,
    SubscribeRequest,
    SubscriptionOut,
)
from app.services.billing_service import BillingService
from app.services.stripe_service import StripeService

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.get("/plans", response_model=list[PlanOut])
async def list_plans(
    _: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[PlanOut]:
    return BillingService(session).list_plans()


@router.get("/subscription", response_model=SubscriptionOut)
async def get_subscription(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SubscriptionOut:
    return BillingService(session).get_subscription(current_user)


@router.post("/checkout", response_model=CheckoutOut)
async def create_checkout(
    payload: CheckoutRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CheckoutOut:
    checkout_url = await StripeService(session).create_checkout_session(
        current_user,
        payload.planId,
        payload.returnBaseUrl,
    )
    return CheckoutOut(checkoutUrl=checkout_url)


@router.post("/checkout/confirm", response_model=SubscriptionOut)
async def confirm_checkout(
    payload: CheckoutConfirmRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SubscriptionOut:
    stripe_service = StripeService(session)
    await stripe_service.confirm_checkout_session(current_user, payload.sessionId)
    return BillingService(session).get_subscription(current_user)


@router.post("/subscribe", response_model=SubscriptionOut)
async def subscribe(
    payload: SubscribeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SubscriptionOut:
    return await BillingService(session).subscribe(current_user, payload.planId)


@router.get("/payments", response_model=list[PaymentOut])
async def list_payments(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[PaymentOut]:
    return await BillingService(session).list_payments(current_user)


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    stripe_service = StripeService(session)
    event = stripe_service.construct_webhook_event(payload, signature)
    await stripe_service.handle_webhook_event(event)
    return JSONResponse(content={"received": True})
