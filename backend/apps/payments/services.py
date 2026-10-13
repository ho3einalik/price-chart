from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from .models import PaymentTransaction, PaymentVerificationStatus
from apps.orders.models import Order, PaymentStatus
from apps.audit.services import record_audit_event

@transaction.atomic
def verify_payment_transaction(payment, user):
    """Manually approves card-to-card or gateway transaction and syncs order payment status idempotently"""
    payment = PaymentTransaction.objects.select_for_update().get(id=payment.id)
    if payment.status == PaymentVerificationStatus.VERIFIED:
        return payment

    # Lock order and check total verified payments to prevent overpayment race conditions
    order = Order.objects.select_for_update().get(id=payment.order_id)
    total_verified = sum(
        p.amount for p in order.payments.filter(status=PaymentVerificationStatus.VERIFIED)
    )

    if total_verified + payment.amount > order.grand_total:
        from rest_framework.exceptions import ValidationError
        raise ValidationError(
            f"تأیید این تراکنش باعث پرداخت بیش از سقف سفارش خواهد شد. مجموع تأییدشده: {total_verified}، تراکنش فعلی: {payment.amount}، مبلغ کل: {order.grand_total}"
        )

    payment.status = PaymentVerificationStatus.VERIFIED
    payment.verified_by = user
    payment.verified_at = timezone.now()
    payment.save()

    new_total_verified = total_verified + payment.amount
    if new_total_verified >= order.grand_total:
        order.payment_status = PaymentStatus.PAID
    elif new_total_verified > 0:
        order.payment_status = PaymentStatus.PARTIALLY_PAID
    else:
        order.payment_status = PaymentStatus.PENDING
    order.save()

    record_audit_event(
        store=payment.store,
        user=user,
        action="PAYMENT_VERIFIED",
        target_type="PaymentTransaction",
        target_id=str(payment.id),
        changes={'order_number': order.order_number, 'amount': str(payment.amount), 'order_payment_status': order.payment_status}
    )
    return payment

@transaction.atomic
def reject_payment_transaction(payment, reason, user):
    """Rejects card-to-card payment transaction with reason idempotently"""
    payment = PaymentTransaction.objects.select_for_update().get(id=payment.id)
    if payment.status == PaymentVerificationStatus.REJECTED:
        return payment

    payment.status = PaymentVerificationStatus.REJECTED
    payment.rejection_reason = reason
    payment.verified_by = user
    payment.verified_at = timezone.now()
    payment.save()

    order = Order.objects.select_for_update().get(id=payment.order_id)
    total_verified = sum(
        p.amount for p in order.payments.filter(status=PaymentVerificationStatus.VERIFIED)
    )
    if total_verified == 0:
        order.payment_status = PaymentStatus.PENDING
    elif total_verified < order.grand_total:
        order.payment_status = PaymentStatus.PARTIALLY_PAID
    order.save()

    record_audit_event(
        store=payment.store,
        user=user,
        action="PAYMENT_REJECTED",
        target_type="PaymentTransaction",
        target_id=str(payment.id),
        changes={'order_number': order.order_number, 'reason': reason}
    )
    return payment


@transaction.atomic
def process_payment_refund(payment, amount=None, reason="", user=None):
    """
    Safely and idempotently refunds a verified payment transaction.
    Pessimistically locks PaymentTransaction and Order to prevent over-refunds.
    """
    from rest_framework.exceptions import ValidationError
    payment = PaymentTransaction.objects.select_for_update().get(id=payment.id)
    if payment.status != PaymentVerificationStatus.VERIFIED:
        raise ValidationError("تنها تراکنش‌های تأییدشده قابل استرداد (ریفاند) هستند.")

    order = Order.objects.select_for_update().get(id=payment.order_id)
    refund_amount = Decimal(str(amount)) if amount is not None else payment.amount

    if refund_amount <= 0:
        raise ValidationError("مبلغ استرداد باید بزرگتر از صفر باشد.")

    if refund_amount > payment.amount:
        raise ValidationError(
            f"مبلغ درخواستی برای استرداد ({refund_amount}) نمی‌تواند از مبلغ تراکنش ({payment.amount}) بیشتر باشد."
        )

    # Calculate remaining verified across order excluding this one
    remaining_verified = sum(
        p.amount for p in order.payments.filter(status=PaymentVerificationStatus.VERIFIED).exclude(id=payment.id)
    )

    payment.status = PaymentVerificationStatus.REFUNDED
    payment.rejection_reason = f"مسترد شده: {reason}" if reason else "مسترد شده توسط کاربر"
    payment.save(update_fields=['status', 'rejection_reason', 'updated_at'])

    # Recalculate order payment status
    if remaining_verified == 0:
        order.payment_status = PaymentStatus.REFUNDED
    elif remaining_verified < order.grand_total:
        order.payment_status = PaymentStatus.PARTIALLY_PAID
    else:
        order.payment_status = PaymentStatus.PAID
    order.save(update_fields=['payment_status', 'updated_at'])

    record_audit_event(
        store=payment.store,
        user=user,
        action="PAYMENT_REFUNDED",
        target_type="PaymentTransaction",
        target_id=str(payment.id),
        changes={'order_number': order.order_number, 'refund_amount': str(refund_amount), 'reason': reason}
    )
    return payment

