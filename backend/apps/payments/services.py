from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from .models import PaymentTransaction, PaymentVerificationStatus
from apps.orders.models import PaymentStatus
from apps.audit.services import record_audit_event

@transaction.atomic
def verify_payment_transaction(payment, user):
    """Manually approves card-to-card or gateway transaction and syncs order payment status"""
    payment.status = PaymentVerificationStatus.VERIFIED
    payment.verified_by = user
    payment.verified_at = timezone.now()
    payment.save()

    # Recalculate order total verified payments
    order = payment.order
    total_verified = sum(
        p.amount for p in order.payments.filter(status=PaymentVerificationStatus.VERIFIED)
    )

    if total_verified >= order.grand_total:
        order.payment_status = PaymentStatus.PAID
    elif total_verified > 0:
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
    """Rejects card-to-card payment transaction with reason"""
    payment.status = PaymentVerificationStatus.REJECTED
    payment.rejection_reason = reason
    payment.verified_by = user
    payment.verified_at = timezone.now()
    payment.save()

    order = payment.order
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
