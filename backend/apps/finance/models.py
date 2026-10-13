import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.tenancy.models import TenantScopedModel

class ExpenseCategory(models.TextChoices):
    PACKAGING = 'PACKAGING', 'بسته‌بندی و پاکت'
    SHIPPING = 'SHIPPING', 'هزینه ارسال و پیک'
    MARKETING = 'MARKETING', 'تبلیغات و بازاریابی'
    SALARY = 'SALARY', 'حقوق و دستمزد پرسنل'
    RENT = 'RENT', 'اجاره‌بها و شارژ انبار/دفتر'
    PLATFORM_FEE = 'PLATFORM_FEE', 'کارمزد درگاه و اشتراک‌ها'
    TAX = 'TAX', 'مالیات و عوارض'
    OTHER = 'OTHER', 'سایر هزینه‌های جاری'

class Expense(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, verbose_name="عنوان هزینه")
    category = models.CharField(
        max_length=30,
        choices=ExpenseCategory.choices,
        default=ExpenseCategory.OTHER,
        verbose_name="دسته‌بندی هزینه"
    )
    amount = models.DecimalField(max_digits=14, decimal_places=0, verbose_name="مبلغ هزینه")
    currency = models.CharField(max_length=10, default='IRT', verbose_name="واحد پول")
    incurred_at = models.DateField(default=timezone.now, verbose_name="تاریخ وقوع هزینه")
    receipt_image_url = models.CharField(max_length=1000, blank=True, verbose_name="تصویر فاکتور / رسید")
    notes = models.TextField(blank=True, verbose_name="توضیحات و بابت")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = 'هزینه عملیاتی'
        verbose_name_plural = 'هزینه‌های عملیاتی'
        ordering = ['-incurred_at', '-created_at']

    def __str__(self):
        return f"{self.title}: {self.amount} {self.currency} ({self.get_category_display()})"


class GatewaySettlement(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gateway_name = models.CharField(max_length=50, default='ZARINPAL', verbose_name="نام درگاه پرداخت")
    settlement_date = models.DateField(default=timezone.now, verbose_name="تاریخ تسویه بانکی")
    gross_amount = models.DecimalField(max_digits=14, decimal_places=0, verbose_name="مبلغ ناخالص تراکنش‌ها")
    gateway_fee = models.DecimalField(max_digits=14, decimal_places=0, default=Decimal('0'), verbose_name="کارمزد کسرشده درگاه")
    net_deposited_amount = models.DecimalField(max_digits=14, decimal_places=0, verbose_name="مبلغ خالص واریزشده به حساب")
    sheba_number = models.CharField(max_length=34, blank=True, verbose_name="شماره شبا واریزی")
    tracking_reference = models.CharField(max_length=100, blank=True, verbose_name="شناسه پیگیری شاپرک / بانکی")
    is_reconciled = models.BooleanField(default=True, verbose_name="تطبیق داده شده")
    discrepancy_amount = models.DecimalField(max_digits=14, decimal_places=0, default=Decimal('0'), verbose_name="مبلغ مغایرت")
    notes = models.TextField(blank=True, verbose_name="یادداشت تسویه")

    class Meta:
        verbose_name = 'تسویه درگاه پرداخت'
        verbose_name_plural = 'تسویه‌های درگاه‌های پرداخت'
        ordering = ['-settlement_date', '-created_at']

    def __str__(self):
        return f"تسویه {self.gateway_name}: {self.net_deposited_amount:,} تومان ({self.settlement_date})"


class DebtEntityType(models.TextChoices):
    SUPPLIER_DEBT = 'SUPPLIER_DEBT', 'بدهی به تأمین‌کننده (سفارش خرید PO)'
    CUSTOMER_CREDIT = 'CUSTOMER_CREDIT', 'مطالبه یا بستانکاری مشتری'


class DebtStatus(models.TextChoices):
    PENDING = 'PENDING', 'سررسید نشده / معوق'
    PARTIALLY_PAID = 'PARTIALLY_PAID', 'تسویه جزئی'
    SETTLED = 'SETTLED', 'تسویه کامل'
    OVERDUE = 'OVERDUE', 'دارای تأخیر سررسید'


class AccountsPayableReceivable(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entity_type = models.CharField(max_length=20, choices=DebtEntityType.choices, default=DebtEntityType.SUPPLIER_DEBT)
    supplier = models.ForeignKey('suppliers.Supplier', on_delete=models.SET_NULL, null=True, blank=True, related_name='debts')
    customer = models.ForeignKey('orders.Customer', on_delete=models.SET_NULL, null=True, blank=True, related_name='credits')
    title = models.CharField(max_length=250, verbose_name="شرح بدهی / بستانکاری")
    total_amount = models.DecimalField(max_digits=14, decimal_places=0, verbose_name="مبلغ کل بدهی")
    paid_amount = models.DecimalField(max_digits=14, decimal_places=0, default=Decimal('0'), verbose_name="مبلغ پرداخت‌شده")
    due_date = models.DateField(null=True, blank=True, verbose_name="تاریخ سررسید پرداخت")
    status = models.CharField(max_length=20, choices=DebtStatus.choices, default=DebtStatus.PENDING)
    notes = models.TextField(blank=True, verbose_name="یادداشت")

    class Meta:
        verbose_name = 'بدهی و مطالبات تجاری'
        verbose_name_plural = 'بدهی‌ها و مطالبات تجاری'
        ordering = ['due_date', '-created_at']

    @property
    def remaining_balance(self):
        return max(Decimal('0'), self.total_amount - self.paid_amount)

    def __str__(self):
        return f"{self.title}: مانده {self.remaining_balance:,} تومان ({self.get_status_display()})"


class RefundStatus(models.TextChoices):
    PENDING = 'PENDING', 'در انتظار واریز پایا'
    COMPLETED = 'COMPLETED', 'واریز موفق به حساب مشتری'
    FAILED = 'FAILED', 'ناموفق'


class RefundRecord(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='refund_records', verbose_name="سفارش")
    amount = models.DecimalField(max_digits=14, decimal_places=0, verbose_name="مبلغ استرداد شده")
    destination_card_or_sheba = models.CharField(max_length=34, verbose_name="شماره کارت یا شبای مقصد")
    tracking_code = models.CharField(max_length=100, blank=True, verbose_name="کد پیگیری پایا / حواله")
    status = models.CharField(max_length=20, choices=RefundStatus.choices, default=RefundStatus.COMPLETED)
    reason = models.TextField(blank=True, verbose_name="علت عودت وجه")
    processed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    processed_at = models.DateTimeField(default=timezone.now, verbose_name="زمان استرداد")

    class Meta:
        verbose_name = 'سند استرداد وجه (Refund)'
        verbose_name_plural = 'اسناد استرداد وجه (Refunds)'
        ordering = ['-processed_at']

    def __str__(self):
        return f"استرداد {self.amount:,} تومان برای سفارش {self.order.order_number}"

