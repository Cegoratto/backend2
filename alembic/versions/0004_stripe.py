"""stripe billing fields

Revision ID: 0004_stripe
Revises: 0003_billing
Create Date: 2026-08-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_stripe"
down_revision: Union[str, None] = "0003_billing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("stripe_customer_id", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True))
    op.create_unique_constraint("uq_users_stripe_customer_id", "users", ["stripe_customer_id"])
    op.create_unique_constraint("uq_users_stripe_subscription_id", "users", ["stripe_subscription_id"])

    op.add_column("payments", sa.Column("stripe_checkout_session_id", sa.String(length=255), nullable=True))
    op.add_column("payments", sa.Column("stripe_invoice_id", sa.String(length=255), nullable=True))
    op.create_unique_constraint(
        "uq_payments_stripe_checkout_session_id",
        "payments",
        ["stripe_checkout_session_id"],
    )
    op.create_unique_constraint("uq_payments_stripe_invoice_id", "payments", ["stripe_invoice_id"])


def downgrade() -> None:
    op.drop_constraint("uq_payments_stripe_invoice_id", "payments", type_="unique")
    op.drop_constraint("uq_payments_stripe_checkout_session_id", "payments", type_="unique")
    op.drop_column("payments", "stripe_invoice_id")
    op.drop_column("payments", "stripe_checkout_session_id")

    op.drop_constraint("uq_users_stripe_subscription_id", "users", type_="unique")
    op.drop_constraint("uq_users_stripe_customer_id", "users", type_="unique")
    op.drop_column("users", "stripe_subscription_id")
    op.drop_column("users", "stripe_customer_id")
