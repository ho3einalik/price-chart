import logging
from datetime import timedelta
from django.utils import timezone
from celery import shared_task
from .models import AbandonedCart, AbandonedCartStatus, RecoveryDeliveryStatus
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
        delivery_status__in=[
            RecoveryDeliveryStatus.NOT_SENT,
            RecoveryDeliveryStatus.FAILED,
            RecoveryDeliveryStatus.NOT_CONFIGURED
        ],
        recovery_attempts__lt=3,
        created_at__lte=two_hours_ago,
        created_at__gte=three_days_ago
    ).select_related('store', 'customer')

    processed = 0
    for cart in pending_carts:
        # Prevent rapid immediate retry on the same cart if already attempted within the last 1 hour
        if cart.recovery_attempts > 0 and cart.updated_at:
            if (timezone.now() - cart.updated_at).total_seconds() < 3600:
                continue

        recipient = cart.phone_or_email
        if recipient and recipient.startswith('09'):
            sms_adapter = get_integration_adapter('sms_gateway')
            store_name = cart.store.name if cart.store else "فروشگاه ما"
            msg = f"سلام، سبد خرید شما در {store_name} منتظر شماست! برای تکمیل سفارش به وب‌سایت مراجعه فرمایید."
            try:
                sms_res = sms_adapter.send_sms(to=recipient, message=msg, store=cart.store)
                res_status = sms_res.get('status')
                if res_status == 'ACCEPTED':
                    cart.delivery_status = RecoveryDeliveryStatus.SENT
                    cart.recovery_sms_sent_at = timezone.now()
                    cart.recovery_attempts += 1
                    cart.last_delivery_error = ''
                    cart.save(update_fields=['delivery_status', 'recovery_sms_sent_at', 'recovery_attempts', 'last_delivery_error', 'updated_at'])
                    processed += 1
                elif res_status == 'SIMULATED':
                    cart.delivery_status = RecoveryDeliveryStatus.SIMULATED
                    cart.recovery_sms_sent_at = timezone.now()
                    cart.recovery_attempts += 1
                    cart.last_delivery_error = 'شبیه‌سازی تستی'
                    cart.save(update_fields=['delivery_status', 'recovery_sms_sent_at', 'recovery_attempts', 'last_delivery_error', 'updated_at'])
                elif res_status == 'NOT_CONFIGURED':
                    cart.delivery_status = RecoveryDeliveryStatus.NOT_CONFIGURED
                    cart.recovery_attempts += 1
                    cart.last_delivery_error = sms_res.get('message', 'درگاه پیامک پیکربندی نشده است.')
                    cart.save(update_fields=['delivery_status', 'recovery_attempts', 'last_delivery_error', 'updated_at'])
                else:
                    cart.delivery_status = RecoveryDeliveryStatus.FAILED
                    cart.recovery_attempts += 1
                    cart.last_delivery_error = str(sms_res.get('error', 'ارسال پیامک با خطا مواجه شد.'))
                    cart.save(update_fields=['delivery_status', 'recovery_attempts', 'last_delivery_error', 'updated_at'])
                    logger.warning(f"SMS gateway returned non-accepted status for cart {cart.id}: {sms_res}")
            except Exception as e:
                cart.delivery_status = RecoveryDeliveryStatus.FAILED
                cart.recovery_attempts += 1
                cart.last_delivery_error = str(e)
                cart.save(update_fields=['delivery_status', 'recovery_attempts', 'last_delivery_error', 'updated_at'])
                logger.error(f"Failed to send abandoned cart SMS for cart {cart.id}: {e}")

    return f"Processed {processed} abandoned carts"
