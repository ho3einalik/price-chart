from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Max, Count
from .models import CustomerProfile, CustomerSegment
from apps.orders.models import Customer, Order, OrderStatus, PaymentStatus

def recalculate_customer_rfm(customer):
    """Calculate exact Recency, Frequency, and Monetary (LTV) metrics for a single customer"""
    orders = Order.objects.filter(
        customer=customer,
        payment_status=PaymentStatus.PAID
    ).exclude(order_status=OrderStatus.CANCELLED)
    
    order_count = orders.count()
    if order_count == 0:
        total_spent = Decimal('0')
        aov = Decimal('0')
        recency = 999
        segment = CustomerSegment.NEW
    else:
        total_spent = orders.aggregate(total=Sum('grand_total'))['total'] or Decimal('0')
        aov = total_spent / order_count
        latest_date = orders.aggregate(latest=Max('created_at'))['latest']
        recency = (timezone.now() - latest_date).days if latest_date else 999

        # RFM Segmentation heuristic
        if order_count >= 4 and recency <= 45:
            segment = CustomerSegment.CHAMPION
        elif order_count >= 2 and recency <= 60:
            segment = CustomerSegment.LOYAL
        elif order_count == 1 and recency <= 30:
            segment = CustomerSegment.NEW
        elif order_count >= 2 and recency > 75:
            segment = CustomerSegment.AT_RISK
        elif recency > 120:
            segment = CustomerSegment.HIBERNATING
        else:
            segment = CustomerSegment.POTENTIAL_LOYALIST

    profile, _ = CustomerProfile.objects.get_or_create(
        store=customer.store,
        customer=customer
    )
    profile.frequency_orders_count = order_count
    profile.monetary_total_spent = total_spent
    profile.average_order_value = aov
    profile.recency_days = recency
    profile.segment = segment
    profile.save()
    return profile

def recalculate_all_store_customers(store):
    customers = Customer.objects.filter(store=store)
    updated = []
    for c in customers:
        updated.append(recalculate_customer_rfm(c))
    return len(updated)
