import csv
import io
import uuid
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from .models import Order, OrderItem, Customer, OrderStatus, PaymentStatus, FulfillmentStatus, OrderChannel
from apps.catalog.models import ProductVariant
from apps.inventory.models import Warehouse
from apps.inventory.services import reserve_stock, release_stock_reservation, commit_stock_sale
from apps.audit.services import record_audit_event

def generate_order_number(store):
    date_str = timezone.now().strftime('%Y%m%d')
    count = Order.objects.filter(store=store, created_at__date=timezone.now().date()).count() + 1
    return f"ORD-{date_str}-{count:04d}"

@transaction.atomic
def create_order(store, customer_data, items_data, warehouse, channel=OrderChannel.MANUAL,
                 shipping_cost=Decimal('0'), discount_amount=Decimal('0'),
                 utm_source='', utm_medium='', utm_campaign='', notes='', user=None):
    """Creates an order, captures cost snapshots, and atomically reserves inventory"""
    from apps.features.services import FeatureService
    FeatureService.enforce_plan_quota(store, 'monthly_orders')

    if warehouse.store_id != store.id:
        raise ValueError("انبار انتخابی متعلق به این فروشگاه نیست.")
    if not items_data:
        raise ValueError("سفارش باید حداقل دارای یک ردیف کالا باشد.")
    if shipping_cost < Decimal('0'):
        raise ValueError("هزینه ارسال نمی‌تواند منفی باشد.")
    if discount_amount < Decimal('0'):
        raise ValueError("مبلغ تخفیف نمی‌تواند منفی باشد.")

    phone = str(customer_data.get('phone_number') or customer_data.get('phone') or '').strip()
    name = str(customer_data.get('full_name') or customer_data.get('name') or '').strip()
    opt_in = customer_data.get('marketing_opt_in', True)

    is_placeholder_phone = (not phone) or phone in ('09000000000', '09999999999', '00000000000')

    if is_placeholder_phone:
        guest_phone = f"GUEST-{uuid.uuid4().hex[:10]}"
        customer = Customer.objects.create(
            store=store,
            phone_number=guest_phone,
            full_name=name or 'مشتری مهمان / حضوری',
            city=customer_data.get('city', ''),
            province=customer_data.get('province', ''),
            address_line=customer_data.get('address_line', '') or customer_data.get('address', ''),
            postal_code=customer_data.get('postal_code', ''),
            email=customer_data.get('email', ''),
            marketing_opt_in=False,
        )
    else:
        customer, created = Customer.objects.get_or_create(
            store=store,
            phone_number=phone,
            defaults={
                'full_name': name or 'مشتری بدون نام',
                'city': customer_data.get('city', ''),
                'province': customer_data.get('province', ''),
                'address_line': customer_data.get('address_line', '') or customer_data.get('address', ''),
                'postal_code': customer_data.get('postal_code', ''),
                'email': customer_data.get('email', ''),
                'marketing_opt_in': opt_in,
            }
        )
        if not created and 'marketing_opt_in' in customer_data and customer.marketing_opt_in != opt_in:
            customer.marketing_opt_in = opt_in
            customer.save(update_fields=['marketing_opt_in', 'updated_at'])

    order_number = generate_order_number(store)
    order = Order.objects.create(
        store=store,
        order_number=order_number,
        channel=channel,
        customer=customer,
        warehouse=warehouse,
        currency=store.currency,
        order_status=OrderStatus.CONFIRMED,
        payment_status=PaymentStatus.PENDING,
        fulfillment_status=FulfillmentStatus.UNFULFILLED,
        shipping_cost=shipping_cost,
        discount_amount=discount_amount,
        utm_source=utm_source,
        utm_medium=utm_medium,
        utm_campaign=utm_campaign,
        notes=notes,
        created_by=user
    )

    total_items = Decimal('0')
    for item in items_data:
        variant_id = item.get('variant_id')
        qty = int(item.get('quantity', 1))
        if qty <= 0:
            raise ValueError("تعداد کالا باید بزرگتر از صفر باشد.")
        unit_price = Decimal(str(item.get('unit_price', 0)))
        if unit_price < Decimal('0'):
            raise ValueError("قیمت واحد نمی‌تواند منفی باشد.")

        variant = ProductVariant.objects.select_related('product').get(id=variant_id, store=store)
        if unit_price <= 0:
            unit_price = variant.retail_price

        # Atomic reservation check
        reserve_stock(
            store=store,
            warehouse=warehouse,
            variant=variant,
            quantity=qty,
            reference=order.order_number,
            user=user
        )

        item_total = (unit_price * qty) - Decimal(str(item.get('unit_discount', 0))) * qty
        total_items += item_total

        OrderItem.objects.create(
            order=order,
            variant=variant,
            variant_sku=variant.sku,
            variant_name=f"{variant.product.name} ({variant.name})",
            quantity=qty,
            unit_price=unit_price,
            cost_price_snapshot=variant.cost_price,  # Historical margin preservation!
            unit_discount=Decimal(str(item.get('unit_discount', 0))),
            total_price=item_total
        )

    order.total_items_price = total_items
    order.grand_total = max(Decimal('0'), total_items + shipping_cost - discount_amount)
    order.save()

    record_audit_event(
        store=store,
        user=user,
        action="ORDER_CREATED",
        target_type="Order",
        target_id=str(order.id),
        changes={'order_number': order.order_number, 'grand_total': str(order.grand_total)}
    )

    def _dispatch_order_created():
        try:
            from apps.automation.services import trigger_automation
            from apps.automation.models import TriggerEvent
            trigger_automation(
                store=store,
                trigger_event=TriggerEvent.ORDER_CREATED,
                payload={
                    'order_id': str(order.id),
                    'order_number': order.order_number,
                    'customer_name': customer.full_name,
                    'customer_phone': customer.phone_number,
                    'grand_total': float(order.grand_total),
                    'items_count': len(items_data),
                    'idempotency_key': f"order_created_{order.id}"
                }
            )
        except Exception:
            pass

    transaction.on_commit(_dispatch_order_created)
    return order

@transaction.atomic
def cancel_order(order, reason='', user=None):
    """Cancels order and releases reserved inventory. Rejects cancellation of fulfilled orders."""
    if order.order_status in [OrderStatus.CANCELLED, OrderStatus.COMPLETED, OrderStatus.FULFILLED] or order.fulfillment_status == FulfillmentStatus.FULFILLED:
        raise ValueError(
            f"سفارش با وضعیت {order.get_order_status_display()} قابل لغو مستقیم نیست. "
            "برای سفارش‌های ارسال‌شده، از فرآیند ثبت مرجوعی (RMA) استفاده نمایید."
        )

    order = Order.objects.select_for_update().get(id=order.id)
    if order.order_status in [OrderStatus.CANCELLED, OrderStatus.COMPLETED, OrderStatus.FULFILLED] or order.fulfillment_status == FulfillmentStatus.FULFILLED:
        raise ValueError(f"سفارش با وضعیت {order.get_order_status_display()} قابل لغو نیست.")

    # Release reservations for each item
    for item in order.items.all():
        release_stock_reservation(
            store=order.store,
            warehouse=order.warehouse,
            variant=item.variant,
            quantity=item.quantity,
            reference=order.order_number,
            user=user
        )

    old_status = order.order_status
    order.order_status = OrderStatus.CANCELLED
    order.save()

    record_audit_event(
        store=order.store,
        user=user,
        action="ORDER_CANCELLED",
        target_type="Order",
        target_id=str(order.id),
        changes={'old_status': old_status, 'new_status': OrderStatus.CANCELLED, 'reason': reason}
    )

    def _dispatch_order_cancelled():
        try:
            from apps.automation.services import trigger_automation
            from apps.automation.models import TriggerEvent
            trigger_automation(
                store=order.store,
                trigger_event=TriggerEvent.ORDER_CANCELLED,
                payload={
                    'order_id': str(order.id),
                    'order_number': order.order_number,
                    'customer_name': order.customer.full_name,
                    'customer_phone': order.customer.phone_number,
                    'grand_total': float(order.grand_total),
                    'idempotency_key': f"order_cancelled_{order.id}"
                }
            )
        except Exception:
            pass

    transaction.on_commit(_dispatch_order_cancelled)
    return order

@transaction.atomic
def fulfill_order(order, tracking_number='', shipping_cost=None, user=None):
    """Commits reserved stock to permanent sale and marks order fulfilled. Idempotent against duplicate requests."""
    if order.order_status == OrderStatus.CANCELLED:
        raise ValueError("سفارش لغو شده قابل ارسال نیست.")

    # Idempotent return if already fulfilled
    if order.order_status in [OrderStatus.FULFILLED, OrderStatus.COMPLETED] or order.fulfillment_status == FulfillmentStatus.FULFILLED:
        from apps.fulfillment.models import Shipment
        existing_shipment = Shipment.objects.filter(order=order).first()
        return order, existing_shipment

    order = Order.objects.select_for_update().get(id=order.id)
    if order.order_status in [OrderStatus.FULFILLED, OrderStatus.COMPLETED] or order.fulfillment_status == FulfillmentStatus.FULFILLED:
        from apps.fulfillment.models import Shipment
        existing_shipment = Shipment.objects.filter(order=order).first()
        return order, existing_shipment

    for item in order.items.all():
        commit_stock_sale(
            store=order.store,
            warehouse=order.warehouse,
            variant=item.variant,
            quantity=item.quantity,
            reference=order.order_number,
            user=user
        )

    order.order_status = OrderStatus.FULFILLED
    order.fulfillment_status = FulfillmentStatus.FULFILLED
    order.save()

    # Record shipment using fulfillment service with idempotency key
    from apps.fulfillment.services import create_shipment
    from apps.fulfillment.models import Carrier
    shipment = create_shipment(
        store=order.store,
        order=order,
        tracking_number=tracking_number or f"TRK-{str(order.id)[:8].upper()}",
        carrier=Carrier.IRPOST,
        shipping_cost=shipping_cost if shipping_cost is not None else order.shipping_cost,
        idempotency_key=f"ship_{order.id}"
    )

    record_audit_event(
        store=order.store,
        user=user,
        action="ORDER_FULFILLED",
        target_type="Order",
        target_id=str(order.id),
        changes={'tracking_number': shipment.tracking_number}
    )

    def _dispatch_order_fulfilled():
        try:
            from apps.automation.services import trigger_automation
            from apps.automation.models import TriggerEvent
            trigger_automation(
                store=order.store,
                trigger_event=TriggerEvent.ORDER_FULFILLED,
                payload={
                    'order_id': str(order.id),
                    'order_number': order.order_number,
                    'customer_name': order.customer.full_name,
                    'customer_phone': order.customer.phone_number,
                    'tracking_number': shipment.tracking_number,
                    'idempotency_key': f"order_fulfilled_{order.id}"
                }
            )
        except Exception:
            pass

    transaction.on_commit(_dispatch_order_fulfilled)
    return order, shipment

def import_orders_from_csv(store, file_content, user=None):
    """
    Parses and validates CSV with columns:
    customer_name, customer_phone, sku, quantity, unit_price, channel, city, address
    Returns dict with summary: created, skipped, errors.
    """
    decoded = file_content.decode('utf-8-sig') if isinstance(file_content, bytes) else file_content
    reader = csv.DictReader(io.StringIO(decoded))

    created_count = 0
    errors = []
    default_warehouse = Warehouse.objects.filter(store=store, is_active=True).first()
    if not default_warehouse:
        default_warehouse = Warehouse.objects.create(store=store, name="انبار مرکزی", is_default=True)

    row_index = 1
    for row in reader:
        row_index += 1
        phone = row.get('customer_phone', '').strip()
        name = row.get('customer_name', '').strip()
        sku = row.get('sku', '').strip()
        qty_str = row.get('quantity', '1').strip()
        price_str = row.get('unit_price', '0').strip()
        channel = row.get('channel', 'MANUAL').strip().upper()

        if not phone or not sku:
            errors.append({'row': row_index, 'error': 'شماره تماس یا کد SKU خالی است.'})
            continue

        try:
            qty = int(qty_str)
            price = Decimal(price_str)
        except Exception:
            errors.append({'row': row_index, 'error': f'مقدار عددی تعداد یا قیمت نامعتبر است: {qty_str}, {price_str}'})
            continue

        variant = ProductVariant.objects.filter(store=store, sku=sku).first()
        if not variant:
            errors.append({'row': row_index, 'error': f'تنوع کالا با کد SKU={sku} یافت نشد.'})
            continue

        try:
            create_order(
                store=store,
                customer_data={
                    'full_name': name or 'مشتری ایمپورت شده',
                    'phone_number': phone,
                    'city': row.get('city', ''),
                    'address_line': row.get('address', ''),
                },
                items_data=[{
                    'variant_id': str(variant.id),
                    'quantity': qty,
                    'unit_price': price if price > 0 else variant.retail_price,
                }],
                warehouse=default_warehouse,
                channel=channel if channel in OrderChannel.values else OrderChannel.MANUAL,
                user=user
            )
            created_count += 1
        except Exception as e:
            errors.append({'row': row_index, 'error': str(e)})

    return {
        'total_rows': row_index - 1,
        'created': created_count,
        'failed': len(errors),
        'errors': errors
    }
