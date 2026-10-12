import uuid
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.orders.models import Order, OrderItem, Customer, OrderChannel, OrderStatus, PaymentStatus, FulfillmentStatus
from apps.catalog.models import ProductVariant
from apps.inventory.models import Warehouse
from apps.inventory.services import commit_stock_sale, get_or_create_balance, reserve_stock
from apps.payments.models import PaymentTransaction, PaymentMethod, PaymentVerificationStatus
from apps.audit.services import record_audit_event
from apps.finance.models import AccountsPayableReceivable, DebtEntityType, DebtStatus
from .models import B2BClientProfile, VolumeTierDiscount, POSTerminal, POSRegisterSession, POSSessionStatus, ProformaInvoice, ProformaStatus, B2BTier

def calculate_b2b_price(variant, quantity, client=None):
    """
    Calculate applicable unit price considering MOQ / Volume Tier discounts and B2B VIP tiers.
    """
    # 1. Volume Tier Discount (MOQ)
    vol_tier = VolumeTierDiscount.objects.filter(
        variant=variant,
        min_quantity__lte=quantity
    ).order_by('-min_quantity').first()

    base_price = vol_tier.unit_price if vol_tier else variant.retail_price

    # 2. Client tier-based discount
    if client and client.tier:
        tier_discounts = {
            B2BTier.VIP: Decimal('0.15'),
            B2BTier.GOLD: Decimal('0.10'),
            B2BTier.SILVER: Decimal('0.05'),
            B2BTier.STANDARD: Decimal('0.00'),
        }
        discount_rate = tier_discounts.get(client.tier, Decimal('0.00'))
        final_price = round(base_price * (Decimal('1') - discount_rate))
        return max(Decimal('0'), final_price)

    return base_price


@transaction.atomic
def pos_quick_checkout(store, session_id, items_data, customer_phone="09000000000", customer_name="خریدار حضوری", payment_method=PaymentMethod.POS_TERMINAL, user=None, notes=""):
    """
    Real-time In-Person POS quick sale.
    Instantly commits stock sale from terminal warehouse, creates order, and issues payment receipt.
    """
    try:
        session = POSRegisterSession.objects.select_for_update().get(id=session_id, store=store, status=POSSessionStatus.OPEN)
    except POSRegisterSession.DoesNotExist:
        raise ValidationError("شیفت صندوقداری فعال یا بازی برای این پایانه یافت نشد.")

    warehouse = session.terminal.warehouse
    if not warehouse:
        warehouse = Warehouse.objects.filter(store=store).first()
        if not warehouse:
            raise ValidationError("هیچ انباری برای کسر موجودی فروشگاه تعریف نشده است.")

    # Get or create customer
    customer, _ = Customer.objects.get_or_create(
        store=store,
        phone_number=customer_phone,
        defaults={'full_name': customer_name or 'خریدار حضوری'}
    )

    order_number = f"POS-{timezone.now().strftime('%y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    order = Order.objects.create(
        store=store,
        order_number=order_number,
        channel=OrderChannel.POS,
        customer=customer,
        warehouse=warehouse,
        order_status=OrderStatus.COMPLETED,
        payment_status=PaymentStatus.PAID,
        fulfillment_status=FulfillmentStatus.FULFILLED,
        currency=store.currency,
        notes=notes or f"فروش حضوری صندوق {session.terminal.name}",
        created_by=user
    )

    total_amount = Decimal('0')

    for item in items_data:
        variant_id = item.get('variant_id')
        qty = int(item.get('quantity', 1))
        unit_price = Decimal(str(item.get('unit_price', 0)))

        variant = ProductVariant.objects.get(id=variant_id, store=store)
        if unit_price <= 0:
            unit_price = variant.retail_price

        row_total = unit_price * qty
        total_amount += row_total

        # Atomic stock sale deduction from terminal warehouse
        commit_stock_sale(
            store=store,
            warehouse=warehouse,
            variant=variant,
            quantity=qty,
            reference=order.order_number,
            user=user
        )

        OrderItem.objects.create(
            order=order,
            variant=variant,
            variant_sku=variant.sku,
            variant_name=variant.name or variant.product.name,
            quantity=qty,
            unit_price=unit_price,
            cost_price_snapshot=variant.cost_price or Decimal('0'),
            total_price=row_total
        )

    order.total_items_price = total_amount
    order.grand_total = total_amount
    order.save()

    # Create Instant Verified Payment
    PaymentTransaction.objects.create(
        store=store,
        order=order,
        method=payment_method,
        amount=total_amount,
        currency=store.currency,
        status=PaymentVerificationStatus.VERIFIED,
        reference_number=f"POS-{uuid.uuid4().hex[:8].upper()}",
        tracking_code=f"TRK-{uuid.uuid4().hex[:6].upper()}",
        verified_by=user,
        verified_at=timezone.now()
    )

    # Increment session totals
    session.total_sales += total_amount
    session.save()

    record_audit_event(
        store=store,
        user=user,
        action="POS_QUICK_SALE",
        target_type="Order",
        target_id=order.id,
        changes={
            'order_number': order.order_number,
            'grand_total': str(total_amount),
            'terminal': session.terminal.name,
            'items_count': len(items_data)
        }
    )

    return order


@transaction.atomic
def convert_proforma_to_order(proforma, user=None):
    """
    Convert an accepted B2B proforma invoice into a confirmed order,
    reserving warehouse stock and updating client accounts receivable ledger.
    """
    if proforma.status == ProformaStatus.CONVERTED:
        raise ValidationError("این پیش‌فاکتور قبلاً به سفارش نهایی تبدیل شده است.")

    client = proforma.client
    store = proforma.store

    # Credit limit check
    if client.current_debt + proforma.grand_total > client.credit_limit:
        raise ValidationError(
            f"مبلغ این سفارش ({proforma.grand_total:,} تومان) از سقف اعتبار باقیمانده همکار ({client.available_credit:,} تومان) فراتر می‌رود."
        )

    warehouse = Warehouse.objects.filter(store=store).first()
    if not warehouse:
        raise ValidationError("هیچ انباری در فروشگاه ثبت نشده است.")

    order_number = f"B2B-{timezone.now().strftime('%y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    order = Order.objects.create(
        store=store,
        order_number=order_number,
        channel=OrderChannel.MANUAL,
        customer=client.customer,
        warehouse=warehouse,
        order_status=OrderStatus.CONFIRMED,
        payment_status=PaymentStatus.PENDING,
        fulfillment_status=FulfillmentStatus.UNFULFILLED,
        currency=store.currency,
        total_items_price=proforma.subtotal,
        discount_amount=proforma.discount,
        tax_amount=proforma.tax,
        grand_total=proforma.grand_total,
        notes=f"تبدیل‌شده از پیش‌فاکتور {proforma.invoice_number}. {proforma.notes}",
        created_by=user
    )

    # Process items and reserve stock
    for item in proforma.items:
        variant_id = item.get('variant_id')
        qty = int(item.get('quantity', 1))
        unit_price = Decimal(str(item.get('unit_price', 0)))

        variant = ProductVariant.objects.get(id=variant_id, store=store)
        row_total = unit_price * qty

        reserve_stock(
            store=store,
            warehouse=warehouse,
            variant=variant,
            quantity=qty,
            reference=order.order_number,
            user=user
        )

        OrderItem.objects.create(
            order=order,
            variant=variant,
            variant_sku=variant.sku,
            variant_name=variant.name or variant.product.name,
            quantity=qty,
            unit_price=unit_price,
            cost_price_snapshot=variant.cost_price or Decimal('0'),
            total_price=row_total
        )

    # Update Client Debt
    client.current_debt += proforma.grand_total
    client.save()

    # Create Accounts Receivable Record
    due_date = (timezone.now() + timezone.timedelta(days=client.payment_terms_days)).date()
    AccountsPayableReceivable.objects.create(
        store=store,
        entity_type=DebtEntityType.CUSTOMER_CREDIT,
        customer=client.customer,
        title=f"طلب نسیه بابت سفارش عمده {order.order_number} (پیش‌فاکتور {proforma.invoice_number})",
        total_amount=proforma.grand_total,
        paid_amount=Decimal('0'),
        due_date=due_date,
        status=DebtStatus.PENDING,
        notes=f"مشتری همکار: {client.company_name} - مهلت تسویه: {client.payment_terms_days} روز"
    )

    # Mark Proforma as Converted
    proforma.status = ProformaStatus.CONVERTED
    proforma.save()

    record_audit_event(
        store=store,
        user=user,
        action="PROFORMA_CONVERTED_TO_ORDER",
        target_type="ProformaInvoice",
        target_id=proforma.id,
        changes={
            'order_number': order.order_number,
            'client': client.company_name,
            'grand_total': str(proforma.grand_total)
        }
    )

    return order
