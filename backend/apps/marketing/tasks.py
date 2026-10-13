import logging
from datetime import timedelta
from django.utils import timezone
from celery import shared_task
from .models import AbandonedCart, AbandonedCartStatus
from apps.features.adapters import get_integration_adapter

logger = logging.getLogger(__name__)


@shared_task(name='marketing.check_abandoned_carts_and_notify')
def check_abandoned_carts_and_notify():
    """Finds abandoned carts older than 2 hours and sends reminder messages"""
    two_hours_ago = timezone.now() - timedelta(hours=2)
    three_days_ago = timezone.now() - timedelta(days=3)

    pending_carts = AbandonedCart.objects.filter(
        status=AbandonedCartStatus.PENDING,
        recovery_sms_sent_at__isnull=True,
        created_at__lte=two_hours_ago,
        created_at__gte=three_days_ago
    ).select_related('store', 'customer')

    processed = 0
    for cart in pending_carts:
        recipient = cart.phone_or_email
        if recipient and recipient.startswith('09'):
            sms_adapter = get_integration_adapter('sms_gateway')
            store_name = cart.store.name if cart.store else "فروشگاه ما"
            msg = f"سلام، سبد خرید شما در {store_name} منتظر شماست! برای تکمیل سفارش به وب‌سایت مراجعه فرمایید."
            try:
                sms_res = sms_adapter.send_sms(to=recipient, message=msg, store=cart.store)
                if sms_res.get('status') in ['ACCEPTED', 'NOT_CONFIGURED', 'SIMULATED']:
                    cart.recovery_sms_sent_at = timezone.now()
                    cart.save(update_fields=['recovery_sms_sent_at'])
                    processed += 1
                else:
                    logger.warning(f"SMS gateway returned non-accepted status for cart {cart.id}: {sms_res}")
            except Exception as e:
                logger.error(f"Failed to send abandoned cart SMS for cart {cart.id}: {e}")

    return f"Processed {processed} abandoned carts"
