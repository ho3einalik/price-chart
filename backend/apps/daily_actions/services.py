from django.utils import timezone
from datetime import timedelta
from django.db.models import F
from .models import DailyAction, ActionSeverity, ActionStatus
from apps.inventory.models import InventoryBalance
from apps.payments.models import PaymentTransaction, PaymentVerificationStatus
from apps.orders.models import Order, OrderStatus, FulfillmentStatus

def sync_daily_actions_for_store(store):
    """Evaluates business rules against real tenant data and updates Action Center"""
    actions_created_or_updated = []

    # 1. Low Stock Alert
    low_balances = InventoryBalance.objects.filter(
        store=store,
        on_hand_quantity__lte=F('reorder_point') + F('reserved_quantity')
    ).select_related('variant', 'variant__product', 'warehouse')

    low_stock_key = f"LOW_STOCK_{store.id}"
    if low_balances.exists():
        affected_items = [
            {
                'sku': b.variant.sku,
                'name': f"{b.variant.product.name} ({b.variant.name})",
                'warehouse': b.warehouse.name,
                'available': b.available,
                'reorder_point': b.reorder_point,
            }
            for b in low_balances[:10]
        ]
        action, _ = DailyAction.objects.update_or_create(
            store=store,
            action_key=low_stock_key,
            defaults={
                'title': f'کسری موجودی برای {low_balances.count()} قلم کالا',
                'explanation': 'موجودی قابل فروش برخی از اقلام پرفروش به زیر نقطه سفارش مجدد رسیده است و خطر اتمام موجودی وجود دارد.',
                'severity': ActionSeverity.CRITICAL if any(b.available == 0 for b in low_balances) else ActionSeverity.HIGH,
                'suggested_action': 'ثبت سفارش خرید یا انتقال موجودی از انبار دیگر',
                'evidence': {'count': low_balances.count(), 'items': affected_items},
                'status': ActionStatus.NEW,
            }
        )
        actions_created_or_updated.append(action)
    else:
        # If no low balances, auto-resolve existing
        DailyAction.objects.filter(store=store, action_key=low_stock_key, status__in=[ActionStatus.NEW, ActionStatus.IN_PROGRESS]).update(
            status=ActionStatus.RESOLVED,
            resolved_at=timezone.now(),
            resolution_note='موجودی تمام اقلام به سطح مجاز رسید.'
        )

    # 2. Pending Card-to-Card Receipts Alert
    pending_payments = PaymentTransaction.objects.filter(
        store=store,
        status=PaymentVerificationStatus.PENDING_VERIFICATION
    ).select_related('order', 'order__customer')

    pending_payment_key = f"PENDING_PAYMENTS_{store.id}"
    if pending_payments.exists():
        total_pending_amount = sum(p.amount for p in pending_payments)
        evidence_payments = [
            {
                'payment_id': str(p.id),
                'order_number': p.order.order_number,
                'customer': p.order.customer.full_name,
                'amount': int(p.amount),
                'card_mask': p.payer_card_mask,
            }
            for p in pending_payments[:10]
        ]
        action, _ = DailyAction.objects.update_or_create(
            store=store,
            action_key=pending_payment_key,
            defaults={
                'title': f'{pending_payments.count()} فیش کارت‌به‌کارت در انتظار تأیید حسابداری',
                'explanation': f'مبلغ {int(total_pending_amount):,} {store.currency} فیش واریزی توسط مشتریان ثبت شده و نیازمند انطباق با صورتحساب بانکی است.',
                'severity': ActionSeverity.HIGH,
                'suggested_action': 'بررسی کارتابل فیش‌های واریزی و تأیید یا رد تراکنش‌ها',
                'evidence': {'count': pending_payments.count(), 'total_amount': int(total_pending_amount), 'payments': evidence_payments},
                'status': ActionStatus.NEW,
            }
        )
        actions_created_or_updated.append(action)
    else:
        DailyAction.objects.filter(store=store, action_key=pending_payment_key, status__in=[ActionStatus.NEW, ActionStatus.IN_PROGRESS]).update(
            status=ActionStatus.RESOLVED,
            resolved_at=timezone.now(),
            resolution_note='تمامی فیش‌های واریزی تعیین تکلیف شدند.'
        )

    # 3. Delayed Orders Alert (> 24 hours confirmed but unfulfilled)
    cutoff = timezone.now() - timedelta(hours=24)
    delayed_orders = Order.objects.filter(
        store=store,
        order_status=OrderStatus.CONFIRMED,
        fulfillment_status=FulfillmentStatus.UNFULFILLED,
        created_at__lte=cutoff
    ).select_related('customer')

    delayed_orders_key = f"DELAYED_ORDERS_{store.id}"
    if delayed_orders.exists():
        evidence_orders = [
            {
                'order_number': o.order_number,
                'customer': o.customer.full_name,
                'created_at': o.created_at.strftime('%Y/%m/%d %H:%M'),
                'grand_total': int(o.grand_total),
            }
            for o in delayed_orders[:10]
        ]
        action, _ = DailyAction.objects.update_or_create(
            store=store,
            action_key=delayed_orders_key,
            defaults={
                'title': f'{delayed_orders.count()} سفارش با تأخیر در ارسال مواجه شده است',
                'explanation': 'سفارش‌هایی بیش از ۲۴ ساعت است که تأیید شده‌اند اما هنوز بسته‌بندی یا ارسال نشده‌اند.',
                'severity': ActionSeverity.MEDIUM,
                'suggested_action': 'صدور برگه بسته‌بندی و تحویل مرسولات به حامل پستی',
                'evidence': {'count': delayed_orders.count(), 'orders': evidence_orders},
                'status': ActionStatus.NEW,
            }
        )
        actions_created_or_updated.append(action)
    else:
        DailyAction.objects.filter(store=store, action_key=delayed_orders_key, status__in=[ActionStatus.NEW, ActionStatus.IN_PROGRESS]).update(
            status=ActionStatus.RESOLVED,
            resolved_at=timezone.now(),
            resolution_note='سفارش معوقه‌ای وجود ندارد.'
        )

    return actions_created_or_updated
