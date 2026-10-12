import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from apps.tenancy.models import TenantScopedModel
from apps.orders.models import Order, OrderItem, Customer
from apps.catalog.models import ProductVariant

class ReturnReason(models.TextChoices):
    DEFECTIVE = 'DEFECTIVE', 'کالای معیوب یا دارای نقص فنی'
    WRONG_ITEM = 'WRONG_ITEM', 'ارسال کالای اشتباه'
    SIZE_MISMATCH = 'SIZE_MISMATCH', 'عدم تطابق سایز / رنگ'
    CUSTOMER_REMORSE = 'CUSTOMER_REMORSE', 'انصراف خریدار از خرید'
    DAMAGED_IN_TRANSIT = 'DAMAGED_IN_TRANSIT', 'آسیب‌دیدگی در حین حمل و نقل'
    OTHER = 'OTHER', 'سایر دلایل'

class ReturnStatus(models.TextChoices):
    REQUESTED = 'REQUESTED', 'درخواست ثبت شده'
    APPROVED = 'APPROVED', 'تأیید اولیه جهت بازگشت'
    RECEIVED = 'RECEIVED', 'دریافت شده در انبار'
    INSPECTED = 'INSPECTED', 'کارشناسی و بررسی شده'
    COMPLETED = 'COMPLETED', 'تکمیل و بسته شده'
    REJECTED = 'REJECTED', 'رد درخواست'

class RefundStatus(models.TextChoices):
    PENDING = 'PENDING', 'در انتظار استرداد وجه'
    REFUNDED = 'REFUNDED', 'وجه مسترد شد'
    STORE_CREDIT = 'STORE_CREDIT', 'افزایش اعتبار کیف پول'
    NO_REFUND = 'NO_REFUND', 'بدون بازگشت وجه'

class ReturnAction(models.TextChoices):
    RESTOCK = 'RESTOCK', 'بازگشت به موجودی قابل فروش'
    QUARANTINE_SCRAP = 'QUARANTINE_SCRAP', 'قرنطینه / ضایعات'
    REJECT_RETURN_TO_CUSTOMER = 'REJECT_RETURN_TO_CUSTOMER', 'عدم پذیرش و بازگرداندن به مشتری'

class ItemCondition(models.TextChoices):
    NEW_UNOPENED = 'NEW_UNOPENED', 'پلمپ و دست‌نخورده'
    OPENED_GOOD = 'OPENED_GOOD', 'باز شده اما کاملاً سالم'
    DEFECTIVE = 'DEFECTIVE', 'خراب یا معیوب'
    DAMAGED = 'DAMAGED', 'آسیب‌دیده فیزیکی'

class ReturnRequest(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rma_number = models.CharField(max_length=50, db_index=True, verbose_name="شماره مجوز مرجوعی (RMA)")
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='returns', verbose_name="سفارش مربوطه")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='returns', verbose_name="مشتری")
    status = models.CharField(
        max_length=30,
        choices=ReturnStatus.choices,
        default=ReturnStatus.REQUESTED,
        verbose_name="وضعیت مرجوعی"
    )
    refund_status = models.CharField(
        max_length=30,
        choices=RefundStatus.choices,
        default=RefundStatus.PENDING,
        verbose_name="وضعیت استرداد وجه"
    )
    refund_amount = models.DecimalField(max_digits=14, decimal_places=0, default=Decimal('0'), verbose_name="مبلغ استردادی (تومان)")
    customer_notes = models.TextField(blank=True, verbose_name="علت مرجوعی از زبان مشتری")
    staff_notes = models.TextField(blank=True, verbose_name="یادداشت کارشناس فروشگاه")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = 'درخواست مرجوعی (RMA)'
        verbose_name_plural = 'درخواست‌های مرجوعی (RMA)'
        unique_together = ('store', 'rma_number')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.rma_number} - سفارش {self.order.order_number} ({self.get_status_display()})"


class ReturnItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    return_request = models.ForeignKey(ReturnRequest, on_delete=models.CASCADE, related_name='items')
    order_item = models.ForeignKey(OrderItem, on_delete=models.PROTECT, related_name='return_items', verbose_name="ردیف سفارش")
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, related_name='return_items', verbose_name="تنوع کالا")
    quantity = models.PositiveIntegerField(default=1, verbose_name="تعداد مرجوعی")
    reason = models.CharField(max_length=30, choices=ReturnReason.choices, default=ReturnReason.CUSTOMER_REMORSE, verbose_name="دلیل مرجوعی")
    condition = models.CharField(max_length=30, choices=ItemCondition.choices, default=ItemCondition.NEW_UNOPENED, verbose_name="وضعیت سلامت کالا")
    action = models.CharField(max_length=30, choices=ReturnAction.choices, default=ReturnAction.RESTOCK, verbose_name="تصمیم انبارداری")
    is_inspected = models.BooleanField(default=False, verbose_name="بررسی و کارشناسی شده")
    inspection_notes = models.CharField(max_length=255, blank=True, verbose_name="نتیجه کارشناسی")

    class Meta:
        verbose_name = 'کالای مرجوعی'
        verbose_name_plural = 'کالاهای مرجوعی'

    def __str__(self):
        return f"{self.quantity} x {self.variant.sku} ({self.get_reason_display()})"
