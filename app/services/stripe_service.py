import uuid

import stripe
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models.payment import Payment
from app.models.user import User
from app.services.billing_service import PLANS


class StripeService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        stripe.api_key = self.settings.stripe_secret_key

    def _plan_to_price_id(self, plan_id: str) -> str:
        mapping = {
            "pro": self.settings.stripe_price_id_pro,
            "team": self.settings.stripe_price_id_team,
        }
        price_id = mapping.get(plan_id)
        if not price_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown plan")
        return price_id

    def _price_id_to_plan(self, price_id: str | None) -> str | None:
        if not price_id:
            return None
        if price_id == self.settings.stripe_price_id_pro:
            return "pro"
        if price_id == self.settings.stripe_price_id_team:
            return "team"
        return None

    def _ensure_configured(self) -> None:
        if not self.settings.stripe_secret_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Stripe is not configured",
            )

    async def get_or_create_customer(self, user: User) -> str:
        self._ensure_configured()

        if user.stripe_customer_id:
            return user.stripe_customer_id

        customer = stripe.Customer.create(
            email=user.email,
            name=user.name,
            metadata={"user_id": str(user.id)},
        )
        user.stripe_customer_id = customer.id
        await self.session.commit()
        await self.session.refresh(user)
        return customer.id

    async def create_checkout_session(self, user: User, plan_id: str) -> str:
        self._ensure_configured()

        if plan_id not in {"pro", "team"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown plan")

        if user.plan_tier == plan_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You are already on this plan",
            )

        customer_id = await self.get_or_create_customer(user)
        price_id = self._plan_to_price_id(plan_id)
        frontend_url = self.settings.frontend_url.rstrip("/")

        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{frontend_url}/billing?checkout=success",
            cancel_url=f"{frontend_url}/billing?checkout=cancel",
            metadata={"user_id": str(user.id), "plan_id": plan_id},
            subscription_data={"metadata": {"user_id": str(user.id), "plan_id": plan_id}},
        )

        if not session.url:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Stripe did not return a checkout URL",
            )

        return session.url

    async def cancel_subscription(self, user: User) -> None:
        self._ensure_configured()

        if user.stripe_subscription_id:
            stripe.Subscription.cancel(user.stripe_subscription_id)
            user.stripe_subscription_id = None

        user.plan_tier = "free"
        payment = Payment(
            user_id=user.id,
            plan_id="free",
            amount_cents=0,
            status="completed",
        )
        self.session.add(payment)
        await self.session.commit()
        await self.session.refresh(user)

    def construct_webhook_event(self, payload: bytes, signature: str | None):
        self._ensure_configured()

        if not signature:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Stripe signature")

        try:
            return stripe.Webhook.construct_event(
                payload,
                signature,
                self.settings.stripe_webhook_secret,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload") from exc
        except stripe.error.SignatureVerificationError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature") from exc

    async def _get_user_by_id(self, user_id: str) -> User | None:
        try:
            parsed_id = uuid.UUID(user_id)
        except ValueError:
            return None

        result = await self.session.execute(select(User).where(User.id == parsed_id))
        return result.scalar_one_or_none()

    async def _get_user_by_customer_id(self, customer_id: str | None) -> User | None:
        if not customer_id:
            return None

        result = await self.session.execute(select(User).where(User.stripe_customer_id == customer_id))
        return result.scalar_one_or_none()

    async def _record_payment(
        self,
        *,
        user: User,
        plan_id: str,
        amount_cents: int,
        status_value: str,
        checkout_session_id: str | None = None,
        invoice_id: str | None = None,
    ) -> None:
        if checkout_session_id:
            existing = await self.session.execute(
                select(Payment).where(Payment.stripe_checkout_session_id == checkout_session_id)
            )
            if existing.scalar_one_or_none():
                return

        if invoice_id:
            existing = await self.session.execute(
                select(Payment).where(Payment.stripe_invoice_id == invoice_id)
            )
            if existing.scalar_one_or_none():
                return

        payment = Payment(
            user_id=user.id,
            plan_id=plan_id,
            amount_cents=amount_cents,
            status=status_value,
            stripe_checkout_session_id=checkout_session_id,
            stripe_invoice_id=invoice_id,
        )
        self.session.add(payment)

    async def handle_webhook_event(self, event: stripe.Event) -> None:
        event_type = event["type"]
        data_object = event["data"]["object"]

        if event_type == "checkout.session.completed":
            await self._handle_checkout_completed(data_object)
        elif event_type == "customer.subscription.updated":
            await self._handle_subscription_updated(data_object)
        elif event_type == "customer.subscription.deleted":
            await self._handle_subscription_deleted(data_object)
        elif event_type == "invoice.paid":
            await self._handle_invoice_paid(data_object)

        await self.session.commit()

    async def _handle_checkout_completed(self, session: dict) -> None:
        metadata = session.get("metadata") or {}
        user_id = metadata.get("user_id")
        plan_id = metadata.get("plan_id")

        user = await self._get_user_by_id(user_id) if user_id else None
        if user is None:
            user = await self._get_user_by_customer_id(session.get("customer"))

        if user is None or plan_id not in PLANS:
            return

        subscription_id = session.get("subscription")
        if subscription_id:
            user.stripe_subscription_id = subscription_id

        user.plan_tier = plan_id
        plan = PLANS[plan_id]
        await self._record_payment(
            user=user,
            plan_id=plan_id,
            amount_cents=plan.price_usd * 100,
            status_value="completed",
            checkout_session_id=session.get("id"),
        )

    async def _handle_subscription_updated(self, subscription: dict) -> None:
        user = await self._get_user_by_customer_id(subscription.get("customer"))
        if user is None:
            return

        status_value = subscription.get("status")
        if status_value in {"canceled", "unpaid", "incomplete_expired"}:
            user.plan_tier = "free"
            user.stripe_subscription_id = None
            return

        items = subscription.get("items", {}).get("data", [])
        if not items:
            return

        price_id = items[0].get("price", {}).get("id")
        plan_id = self._price_id_to_plan(price_id)
        if plan_id:
            user.plan_tier = plan_id
            user.stripe_subscription_id = subscription.get("id")

    async def _handle_subscription_deleted(self, subscription: dict) -> None:
        user = await self._get_user_by_customer_id(subscription.get("customer"))
        if user is None:
            return

        user.plan_tier = "free"
        user.stripe_subscription_id = None

    async def _handle_invoice_paid(self, invoice: dict) -> None:
        if invoice.get("billing_reason") == "subscription_create":
            return

        user = await self._get_user_by_customer_id(invoice.get("customer"))
        if user is None:
            return

        lines = invoice.get("lines", {}).get("data", [])
        plan_id = user.plan_tier
        if lines:
            price_id = lines[0].get("price", {}).get("id")
            mapped_plan = self._price_id_to_plan(price_id)
            if mapped_plan:
                plan_id = mapped_plan
                user.plan_tier = mapped_plan

        amount_cents = invoice.get("amount_paid", 0)
        await self._record_payment(
            user=user,
            plan_id=plan_id,
            amount_cents=amount_cents,
            status_value="completed",
            invoice_id=invoice.get("id"),
        )
