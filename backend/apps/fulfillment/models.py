import uuid
from decimal import Decimal
from django.db import models
from apps.tenancy.models import TenantScopedModel
from apps.orders.models import Order

class ShipmentStatus(models.TextChoices):
    PENDING = 'PENDING', 'در انتظار بسته‌بندی'
    SHIPPED = 'SHIPPED', 'ارسال شده (تحویل به پست/پیک)'
    IN_TRANSIT = 'IN_TRANSIT', 'در حال حمل'
    DELIVERED = 'DELIVERED', 'تحویل به مشتری'
    RETURNED_TO_SENDER = 'RETURNED_TO_SENDER', 'برگشت به فرستنده'
    FAILED = 'FAILED', 'ناموفق'

class Carrier(models.TextChoices):
    IRPOST = 'IRPOST', 'پست پیشتاز'
    TIPAX = 'TIPAX', 'تیپاکس'
    CHAPAR = 'CHAPAR', 'چاپار'
    LOCAL_COURIER = 'LOCAL_COURIER', 'پیک موتوری درون‌شهری'
    OTHER = 'OTHER', 'سایر'

class Shipment(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='shipments', verbose_name="سفارش")
    tracking_number = models.CharField(max_length=100, db_index=True, verbose_name="کد رهگیری مرسوله")
    carrier = models.CharField(max_length=30, choices=Carrier.choices, default=Carrier.IRPOST, verbose_name="شرکت پستی / حامل")
    status = models.CharField(max_length=30, choices=ShipmentStatus.choices, default=ShipmentStatus.SHIPPED, verbose_name="وضعیت ارسال")
    shipping_cost = models.DecimalField(max_digits=14, decimal_places=0, default=Decimal('0'), verbose_name="هزینه واقعی ارسال")
    shipped_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان ارسال")
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان تحویل")

    class Meta:
        verbose_name = 'مرسوله پستی'
        verbose_name_plural = 'مرسوله‌های پستی'
        ordering = ['-shipped_at']

    def __str__(self):
        return f"{self.tracking_number} for {self.order.order_number} ({self.get_status_display()})"
