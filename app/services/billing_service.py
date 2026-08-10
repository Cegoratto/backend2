from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment
from app.models.user import User
from app.schemas.billing import PaymentOut, PlanOut, SubscriptionOut


@dataclass(frozen=True)
class PlanDefinition:
    id: str
    name: str
    price_usd: int
    description: str


PLANS: dict[str, PlanDefinition] = {
    "free": PlanDefinition(
        id="free",
        name="Free",
        price_usd=0,
        description="Для личных проектов",
    ),
    "pro": PlanDefinition(
        id="pro",
        name="Pro",
        price_usd=10,
        description="Для профессионалов",
    ),
    "team": PlanDefinition(
        id="team",
        name="Team",
        price_usd=50,
        description="Для команд и бизнеса",
    ),
}


def _plan_to_out(plan: PlanDefinition) -> PlanOut:
    return PlanOut(
        id=plan.id,
        name=plan.name,
        priceUsd=plan.price_usd,
        description=plan.description,
    )


def _payment_to_out(payment: Payment) -> PaymentOut:
    plan = PLANS.get(payment.plan_id)
    return PaymentOut(
        id=str(payment.id),
        planId=payment.plan_id,
        planName=plan.name if plan else payment.plan_id,
        amountCents=payment.amount_cents,
        status=payment.status,
        createdAt=payment.created_at.isoformat(),
    )


class BillingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def list_plans(self) -> list[PlanOut]:
        return [_plan_to_out(plan) for plan in PLANS.values()]

    def get_subscription(self, user: User) -> SubscriptionOut:
        plan = PLANS.get(user.plan_tier, PLANS["free"])
        return SubscriptionOut(planId=plan.id, planName=plan.name, priceUsd=plan.price_usd)

    async def subscribe(self, user: User, plan_id: str) -> SubscriptionOut:
        plan = PLANS.get(plan_id)
        if plan is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown plan")

        if plan_id in {"pro", "team"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Use checkout for paid plans",
            )

        if user.plan_tier == plan_id:
            return self.get_subscription(user)

        from app.services.stripe_service import StripeService

        await StripeService(self.session).cancel_subscription(user)
        return self.get_subscription(user)

    async def list_payments(self, user: User) -> list[PaymentOut]:
        result = await self.session.execute(
            select(Payment)
            .where(Payment.user_id == user.id)
            .order_by(Payment.created_at.desc(), Payment.id.desc())
        )
        payments = result.scalars().all()
        return [_payment_to_out(payment) for payment in payments]
