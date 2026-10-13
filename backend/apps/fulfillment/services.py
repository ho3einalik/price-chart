import uuid
from decimal import Decimal
from django.utils import timezone
from apps.fulfillment.models import Shipment, ShipmentStatus, Carrier, ShipmentTrackingEvent, TrackingEventSource
from apps.orders.models import OrderStatus, FulfillmentStatus

class CarrierAdapter:
    carrier_code = 'OTHER'

    def estimate_shipping_cost(self, weight_grams: int, origin_city: str, dest_city: str) -> Decimal:
        raise NotImplementedError

    def get_tracking_url(self, tracking_number: str) -> str:
        return ''

    def query_live_status(self, tracking_number: str) -> dict:
        """
        Graceful adapter: Returns live status if provider is connected,
        or indicates manual mode without crashing.
        """
        return {
            'is_live': False,
            'message': 'اتصال مستقیم وب‌سرویس در دسترس نیست؛ از ثبت رویداد دستی استفاده فرمایید.'
        }


class IranPostAdapter(CarrierAdapter):
    carrier_code = Carrier.IRPOST

    def estimate_shipping_cost(self, weight_grams: int, origin_city: str, dest_city: str) -> Decimal:
        base_rate = Decimal('45000')  # 45,000 Tomans base
        if weight_grams > 1000:
            extra_kg = (weight_grams - 1000) / 1000
            base_rate += Decimal(str(round(extra_kg * 15000)))
        if origin_city != dest_city:
            base_rate += Decimal('15000')  # Intercity tariff
        return base_rate

    def get_tracking_url(self, tracking_number: str) -> str:
        return f"https://tracking.post.ir/?id={tracking_number}"


class TipaxAdapter(CarrierAdapter):
    carrier_code = Carrier.TIPAX

    def estimate_shipping_cost(self, weight_grams: int, origin_city: str, dest_city: str) -> Decimal:
        base_rate = Decimal('65000')  # 65,000 Tomans base for Tipax
        if weight_grams > 2000:
            extra_kg = (weight_grams - 2000) / 1000
            base_rate += Decimal(str(round(extra_kg * 20000)))
        return base_rate

    def get_tracking_url(self, tracking_number: str) -> str:
        return f"https://tipaxco.com/tracking?id={tracking_number}"


class SnappBoxAdapter(CarrierAdapter):
    carrier_code = Carrier.LOCAL_COURIER

    def estimate_shipping_cost(self, weight_grams: int, origin_city: str, dest_city: str) -> Decimal:
        return Decimal('50000')  # Intra-city motor courier average

    def get_tracking_url(self, tracking_number: str) -> str:
        return ''


ADAPTERS = {
    Carrier.IRPOST: IranPostAdapter(),
    Carrier.TIPAX: TipaxAdapter(),
    Carrier.LOCAL_COURIER: SnappBoxAdapter(),
}

def get_carrier_adapter(carrier_code: str) -> CarrierAdapter:
    return ADAPTERS.get(carrier_code, CarrierAdapter())


def create_shipment(store, order, tracking_number: str, carrier: str, shipping_cost: Decimal = Decimal('0'), idempotency_key: str = '', notes: str = '') -> Shipment:
    """
    Creates a shipment for an order with idempotency check to prevent duplicate shipments.
    """
    # 1. Check idempotency if key provided
    if idempotency_key:
        existing = Shipment.objects.filter(store=store, idempotency_key=idempotency_key).first()
        if existing:
            return existing

    # 2. Check duplicate tracking number for this order
    existing_tracking = Shipment.objects.filter(order=order, tracking_number=tracking_number).first()
    if existing_tracking:
        return existing_tracking

    # 3. Create shipment
    shipment = Shipment.objects.create(
        store=store,
        order=order,
        tracking_number=tracking_number,
        carrier=carrier,
        status=ShipmentStatus.SHIPPED,
        shipping_cost=shipping_cost or order.shipping_cost,
        idempotency_key=idempotency_key or f"ship_{order.id}_{tracking_number}",
        notes=notes
    )

    # 4. Create initial tracking event
    ShipmentTrackingEvent.objects.create(
        shipment=shipment,
        status=ShipmentStatus.SHIPPED,
        location=order.store.name,
        description=f"مرسوله تحویل {shipment.get_carrier_display()} شد با کد رهگیری {tracking_number}.",
        source=TrackingEventSource.MANUAL,
        occurred_at=timezone.now()
    )

    # 5. Transition order to FULFILLED if not already
    if order.fulfillment_status != FulfillmentStatus.FULFILLED:
        order.order_status = OrderStatus.FULFILLED
        order.fulfillment_status = FulfillmentStatus.FULFILLED
        order.save(update_fields=['order_status', 'fulfillment_status', 'updated_at'])

    return shipment


def update_shipment_status(shipment: Shipment, new_status: str, location: str = '', description: str = '', failed_reason: str = '', source: str = TrackingEventSource.MANUAL) -> Shipment:
    """
    Updates shipment status, logs tracking event, and handles delivery / failure transitions.
    """
    shipment.status = new_status
    if new_status == ShipmentStatus.DELIVERED:
        shipment.delivered_at = timezone.now()
        # Mark order completed
        if shipment.order.order_status != OrderStatus.COMPLETED:
            shipment.order.order_status = OrderStatus.COMPLETED
            shipment.order.save(update_fields=['order_status', 'updated_at'])
    elif new_status == ShipmentStatus.FAILED:
        shipment.failed_reason = failed_reason or description

    shipment.save(update_fields=['status', 'delivered_at', 'failed_reason', 'updated_at'])

    # Log tracking event
    ShipmentTrackingEvent.objects.create(
        shipment=shipment,
        status=new_status,
        location=location or (shipment.order.customer.city or ''),
        description=description or f"وضعیت مرسوله به {shipment.get_status_display()} تغییر یافت.",
        source=source,
        occurred_at=timezone.now()
    )

    return shipment
