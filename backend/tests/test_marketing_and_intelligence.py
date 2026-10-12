import pytest
from decimal import Decimal
from apps.marketing.models import Coupon, DiscountType
from apps.finance.models import Expense, ExpenseCategory
from apps.crm.services import recalculate_customer_rfm
from apps.intelligence.services import calculate_demand_forecasts, evaluate_order_risk
from apps.orders.models import Order, OrderItem, OrderStatus, PaymentStatus

@pytest.mark.django_db
def test_coupon_validation_and_calculation(store_a):
    coupon = Coupon.objects.create(
        store=store_a,
        code="NOROOZ20",
        discount_type=DiscountType.PERCENTAGE,
        discount_value=Decimal('20'),
        min_order_amount=Decimal('100000'),
        max_discount_amount=Decimal('50000'),
        is_active=True
    )

    # Order below minimum
    is_valid, msg = coupon.is_valid(order_amount=Decimal('80000'))
    assert not is_valid
    assert "حداقل مبلغ سفارش" in msg

    # Order with valid amount (20% of 200,000 = 40,000, capped at 50,000)
    is_valid, _ = coupon.is_valid(order_amount=Decimal('200000'))
    assert is_valid
    discount = coupon.calculate_discount(order_amount=Decimal('200000'))
    assert discount == Decimal('40000')

    # Order with high amount hitting cap (20% of 400,000 = 80,000 -> capped at 50,000)
    discount_capped = coupon.calculate_discount(order_amount=Decimal('400000'))
    assert discount_capped == Decimal('50000')


@pytest.mark.django_db
def test_crm_rfm_calculation(store_a, customer_a, warehouse_a):
    # Customer creates 3 completed orders
    for i in range(3):
        Order.objects.create(
            store=store_a,
            order_number=f"ORD-CRM-{i}",
            customer=customer_a,
            warehouse=warehouse_a,
            order_status=OrderStatus.COMPLETED,
            payment_status=PaymentStatus.PAID,
            total_items_price=Decimal('100000'),
            grand_total=Decimal('100000')
        )

    profile = recalculate_customer_rfm(customer_a)
    assert profile.frequency_orders_count == 3
    assert profile.monetary_total_spent == Decimal('300000')
    assert profile.average_order_value == Decimal('100000')
    assert profile.recency_days == 0
    assert profile.segment in ['CHAMPION', 'LOYAL', 'POTENTIAL_LOYALIST']


@pytest.mark.django_db
def test_demand_forecast_and_order_risk(store_a, warehouse_a, variant_a1, customer_a):
    # Demand forecast check
    forecasts = calculate_demand_forecasts(store_a, period_days=30)
    assert len(forecasts) >= 1
    f = [item for item in forecasts if item['sku'] == variant_a1.sku][0]
    assert 'days_remaining' in f
    assert 'urgency' in f

    # Order risk evaluation
    order = Order.objects.create(
        store=store_a,
        order_number="ORD-RISK-1",
        customer=customer_a,
        warehouse=warehouse_a,
        order_status=OrderStatus.PENDING_CONFIRMATION,
        payment_status=PaymentStatus.PENDING,
        total_items_price=Decimal('5000000'),  # Very high amount
        grand_total=Decimal('5000000')
    )

    risk = evaluate_order_risk(order)
    assert 'risk_score' in risk
    assert 'risk_level' in risk
    assert len(risk['reasons']) > 0
    assert risk['recommendation'] in ['MANUAL_REVIEW', 'CAUTION', 'AUTO_APPROVE']
