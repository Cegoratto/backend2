from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_plans(client: AsyncClient, auth_headers: dict[str, str]):
    response = await client.get("/api/billing/plans", headers=auth_headers)
    assert response.status_code == 200
    plans = response.json()
    assert len(plans) == 3
    assert [plan["id"] for plan in plans] == ["free", "pro", "team"]
    assert plans[1]["priceUsd"] == 10
    assert plans[2]["priceUsd"] == 50


@pytest.mark.asyncio
async def test_subscription_defaults_to_free(client: AsyncClient, auth_headers: dict[str, str]):
    response = await client.get("/api/billing/subscription", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["planId"] == "free"
    assert body["priceUsd"] == 0


@pytest.mark.asyncio
async def test_subscribe_to_paid_plan_requires_checkout(
    client: AsyncClient, auth_headers: dict[str, str]
):
    response = await client.post(
        "/api/billing/subscribe",
        headers=auth_headers,
        json={"planId": "pro"},
    )
    assert response.status_code == 400
    assert response.json()["error"] == "Use checkout for paid plans"


@pytest.mark.asyncio
@patch("app.services.stripe_service.stripe.checkout.Session.create")
@patch("app.services.stripe_service.stripe.Customer.create")
async def test_checkout_returns_stripe_url(
    mock_customer_create: MagicMock,
    mock_session_create: MagicMock,
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    mock_customer_create.return_value = MagicMock(id="cus_test_123")
    mock_session_create.return_value = MagicMock(url="https://checkout.stripe.com/test")

    response = await client.post(
        "/api/billing/checkout",
        headers=auth_headers,
        json={"planId": "pro"},
    )

    assert response.status_code == 200
    assert response.json()["checkoutUrl"] == "https://checkout.stripe.com/test"
    mock_session_create.assert_called_once()


@pytest.mark.asyncio
@patch("app.services.stripe_service.stripe.checkout.Session.create")
@patch("app.services.stripe_service.stripe.Customer.create")
async def test_checkout_uses_return_base_url(
    mock_customer_create: MagicMock,
    mock_session_create: MagicMock,
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    mock_customer_create.return_value = MagicMock(id="cus_test_123")
    mock_session_create.return_value = MagicMock(url="https://checkout.stripe.com/test")

    response = await client.post(
        "/api/billing/checkout",
        headers=auth_headers,
        json={"planId": "pro", "returnBaseUrl": "http://localhost:5174"},
    )

    assert response.status_code == 200
    call_kwargs = mock_session_create.call_args.kwargs
    assert call_kwargs["success_url"] == "http://localhost:5174/billing?checkout=success&session_id={CHECKOUT_SESSION_ID}"
    assert call_kwargs["cancel_url"] == "http://localhost:5174/billing?checkout=cancel"


@pytest.mark.asyncio
@patch("app.services.stripe_service.stripe.checkout.Session.retrieve")
@patch("app.services.stripe_service.stripe.checkout.Session.create")
@patch("app.services.stripe_service.stripe.Customer.create")
async def test_confirm_checkout_updates_subscription(
    mock_customer_create: MagicMock,
    mock_session_create: MagicMock,
    mock_session_retrieve: MagicMock,
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    mock_customer_create.return_value = MagicMock(id="cus_test_123")
    mock_session_create.return_value = MagicMock(url="https://checkout.stripe.com/test")
    mock_session_retrieve.return_value = {
        "id": "cs_test_confirm",
        "customer": "cus_test_123",
        "subscription": "sub_test_confirm",
        "status": "complete",
        "metadata": {"plan_id": "pro"},
    }

    checkout_response = await client.post(
        "/api/billing/checkout",
        headers=auth_headers,
        json={"planId": "pro"},
    )
    assert checkout_response.status_code == 200

    response = await client.post(
        "/api/billing/checkout/confirm",
        headers=auth_headers,
        json={"sessionId": "cs_test_confirm"},
    )

    assert response.status_code == 200
    assert response.json()["planId"] == "pro"

    subscription_response = await client.get("/api/billing/subscription", headers=auth_headers)
    assert subscription_response.json()["planId"] == "pro"

    payments_response = await client.get("/api/billing/payments", headers=auth_headers)
    assert len(payments_response.json()) == 1
    assert payments_response.json()[0]["planId"] == "pro"


@pytest.mark.asyncio
@patch("app.services.stripe_service.stripe.Subscription.cancel")
async def test_subscribe_to_free_creates_payment(
    mock_subscription_cancel: MagicMock,
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    with patch("app.services.stripe_service.stripe.checkout.Session.create") as mock_session_create, patch(
        "app.services.stripe_service.stripe.Customer.create"
    ) as mock_customer_create:
        mock_customer_create.return_value = MagicMock(id="cus_test_123")
        mock_session_create.return_value = MagicMock(url="https://checkout.stripe.com/test")

        await client.post(
            "/api/billing/checkout",
            headers=auth_headers,
            json={"planId": "team"},
        )

    webhook_payload = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_123",
                "customer": "cus_test_123",
                "subscription": "sub_test_123",
                "metadata": {"user_id": "", "plan_id": "team"},
            }
        },
    }

    with patch("app.services.stripe_service.stripe.Webhook.construct_event") as mock_construct:
        mock_construct.return_value = webhook_payload
        webhook_response = await client.post(
            "/api/billing/webhook",
            content=b"{}",
            headers={"stripe-signature": "sig_test"},
        )
        assert webhook_response.status_code == 200

    subscription_response = await client.get("/api/billing/subscription", headers=auth_headers)
    assert subscription_response.status_code == 200
    assert subscription_response.json()["planId"] == "team"

    downgrade_response = await client.post(
        "/api/billing/subscribe",
        headers=auth_headers,
        json={"planId": "free"},
    )
    assert downgrade_response.status_code == 200
    assert downgrade_response.json()["planId"] == "free"

    payments_response = await client.get("/api/billing/payments", headers=auth_headers)
    payments = payments_response.json()
    assert len(payments) >= 2
    payments_by_plan = {payment["planId"]: payment for payment in payments}
    assert payments_by_plan["free"]["amountCents"] == 0
    assert payments_by_plan["team"]["amountCents"] == 5000


@pytest.mark.asyncio
async def test_subscribe_unknown_plan(client: AsyncClient, auth_headers: dict[str, str]):
    response = await client.post(
        "/api/billing/subscribe",
        headers=auth_headers,
        json={"planId": "enterprise"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_billing_requires_auth(client: AsyncClient):
    response = await client.get("/api/billing/plans")
    assert response.status_code == 401


@pytest.mark.asyncio
@patch("app.services.stripe_service.stripe.Webhook.construct_event")
async def test_webhook_subscription_deleted_downgrades_user(
    mock_construct: MagicMock,
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    with patch("app.services.stripe_service.stripe.checkout.Session.create") as mock_session_create, patch(
        "app.services.stripe_service.stripe.Customer.create"
    ) as mock_customer_create:
        mock_customer_create.return_value = MagicMock(id="cus_test_456")
        mock_session_create.return_value = MagicMock(url="https://checkout.stripe.com/test")

        await client.post(
            "/api/billing/checkout",
            headers=auth_headers,
            json={"planId": "pro"},
        )

    mock_construct.return_value = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_456",
                "customer": "cus_test_456",
                "subscription": "sub_test_456",
                "metadata": {"plan_id": "pro"},
            }
        },
    }
    await client.post(
        "/api/billing/webhook",
        content=b"{}",
        headers={"stripe-signature": "sig_test"},
    )

    mock_construct.return_value = {
        "type": "customer.subscription.deleted",
        "data": {"object": {"customer": "cus_test_456"}},
    }
    response = await client.post(
        "/api/billing/webhook",
        content=b"{}",
        headers={"stripe-signature": "sig_test"},
    )
    assert response.status_code == 200

    subscription_response = await client.get("/api/billing/subscription", headers=auth_headers)
    assert subscription_response.json()["planId"] == "free"
