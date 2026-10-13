import uuid
from django.db import models
from django.conf import settings
from apps.tenancy.models import TenantScopedModel
from apps.catalog.models import ProductVariant

class Warehouse(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150, verbose_name="نام انبار")
    code = models.CharField(max_length=50, blank=True, verbose_name="کد انبار")
    address = models.TextField(blank=True, verbose_name="آدرس انبار")
    is_default = models.BooleanField(default=False, verbose_name="انبار پیش‌فرض")
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    class Meta:
        verbose_name = 'انبار'
        verbose_name_plural = 'انبارها'
        unique_together = ('store', 'name')

    def __str__(self):
        return f"{self.name} ({self.store.name})"

class InventoryBalance(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='balances')
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='balances')
    
    on_hand_quantity = models.IntegerField(default=0, verbose_name="موجودی فیزیکی")
    reserved_quantity = models.IntegerField(default=0, verbose_name="موجودی رزرو شده")
    quarantined_quantity = models.IntegerField(default=0, verbose_name="موجودی قرنطینه/مرجوعی")
    incoming_quantity = models.IntegerField(default=0, verbose_name="موجودی در راه")
    reorder_point = models.IntegerField(default=5, verbose_name="نقطه سفارش مجدد")

    class Meta:
        verbose_name = 'موجودی انبار'
        verbose_name_plural = 'موجودی‌های انبار'
        unique_together = ('warehouse', 'variant')
        constraints = [
            models.CheckConstraint(
                condition=models.Q(on_hand_quantity__gte=0),
                name='inventory_on_hand_non_negative'
            ),
            models.CheckConstraint(
                condition=models.Q(reserved_quantity__gte=0),
                name='inventory_reserved_non_negative'
            ),
            models.CheckConstraint(
                condition=models.Q(quarantined_quantity__gte=0),
                name='inventory_quarantined_non_negative'
            ),
        ]



    @property
    def available(self):
        return max(0, self.on_hand_quantity - self.reserved_quantity - self.quarantined_quantity)

    def __str__(self):
        return f"{self.variant.sku} @ {self.warehouse.name}: {self.available} available ({self.on_hand_quantity} on hand)"

class MovementType(models.TextChoices):
    RECEIPT = 'RECEIPT', 'ورود کالا (رسید)'
    SALE = 'SALE', 'خروج کالا (فروش)'
    RESERVATION = 'RESERVATION', 'رزرو موجودی'
    RESERVATION_RELEASE = 'RESERVATION_RELEASE', 'آزادسازی رزرو'
    ADJUSTMENT = 'ADJUSTMENT', 'تعدیل دستی انبار'
    TRANSFER_IN = 'TRANSFER_IN', 'انتقال ورودی از انبار دیگر'
    TRANSFER_OUT = 'TRANSFER_OUT', 'انتقال خروجی به انبار دیگر'
    RETURN = 'RETURN', 'مرجوعی به انبار'
    DAMAGE = 'DAMAGE', 'ضایعات / خسارت'

class InventoryMovement(TenantScopedModel):
    """Immutable double-entry inventory ledger"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='movements')
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='movements')
    movement_type = models.CharField(max_length=30, choices=MovementType.choices, db_index=True, verbose_name="نوع تراکنش")
    quantity = models.IntegerField(verbose_name="تعداد تغییر (مثبت یا منفی)")
    balance_after = models.IntegerField(verbose_name="موجودی فیزیکی پس از تراکنش")
    reference = models.CharField(max_length=150, blank=True, verbose_name="شماره سند / مرجع (سفارش و غیره)")
    reason = models.CharField(max_length=255, blank=True, verbose_name="دلیل یا شرح")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="کاربر ثبت‌کننده")

    class Meta:
        verbose_name = 'گردش انبار'
        verbose_name_plural = 'گردش‌های انبار'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.movement_type}] {self.quantity} x {self.variant.sku} @ {self.warehouse.name}"
