import logging
from django.db.models import F
from celery import shared_task
from .models import InventoryBalance
from apps.automation.models import TriggerEvent
from apps.automation.services import trigger_automation

logger = logging.getLogger(__name__)


@shared_task(name='inventory.check_low_stock_and_alert')
def check_low_stock_and_alert():
    """Finds inventory items below reorder point and fires STOCK_LOW automation events"""
    low_balances = InventoryBalance.objects.filter(
        on_hand_quantity__lte=F('reorder_point'),
        reorder_point__gt=0
    ).select_related('store', 'warehouse', 'variant', 'variant__product')

    alerted = 0
    for balance in low_balances:
        payload = {
            'event_id': f"stock-low-{balance.id}-{balance.on_hand_quantity}",
            'variant_sku': balance.variant.sku,
            'variant_name': str(balance.variant),
            'warehouse': balance.warehouse.name,
            'on_hand': balance.on_hand_quantity,
            'reorder_point': balance.reorder_point,
            'message': f"موجودی {balance.variant.sku} در انبار {balance.warehouse.name} به {balance.on_hand_quantity} رسید (نقطه سفارش: {balance.reorder_point})."
        }
        try:
            trigger_automation(
                store=balance.store,
                trigger_event=TriggerEvent.STOCK_LOW,
                payload=payload
            )
            alerted += 1
        except Exception as e:
            logger.error(f"Failed to trigger STOCK_LOW automation for balance {balance.id}: {e}")

    return f"Triggered {alerted} low stock alerts"
