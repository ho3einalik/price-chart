import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from apps.tenancy.models import TenantScopedModel
from apps.orders.models import Customer
from apps.catalog.models import ProductVariant
from apps.inventory.models import Warehouse

class B2BTier(models.TextChoices):
    STANDARD = 'STANDARD', 'عادی همکار'
    SILVER = 'SILVER', 'نقره‌ای'
    GOLD = 'GOLD', 'طلایی'
    VIP = 'VIP', 'نمایندگی رسمی'


class B2BClientProfile(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.OneToOneField(Customer, on_delete=models.CASCADE, related_name='b2b_profile', verbose_name="مشتری مرتبط")
    company_name = models.CharField(max_length=200, verbose_name="نام شرکت / فروشگاه همکار")
    economic_code = models.CharField(max_length=50, blank=True, verbose_name="شناسه ملی / کد اقتصادی")
    credit_limit = models.DecimalField(max_digits=14, decimal_places=0, default=Decimal('0'), verbose_name="سقف اعتبار خرید نسیه (تومان)")
    current_debt = models.DecimalField(max_digits=14, decimal_places=0, default=Decimal('0'), verbose_name="بدهی تسویه‌نشده (تومان)")
    payment_terms_days = models.PositiveIntegerField(default=30, verbose_name="مهلت پرداخت (روز)")
    tier = models.CharField(max_length=20, choices=B2BTier.choices, default=B2BTier.STANDARD, verbose_name="سطح همکاری B2B")
    is_approved = models.BooleanField(default=True, verbose_name="تایید شده توسط مدیریت")
    notes = models.TextField(blank=True, verbose_name="یادداشت‌های اعتبارسنجی")

    class Meta:
        verbose_name = 'پروفایل همکار عمده‌فروشی'
        verbose_name_plural = 'پروفایل‌های همکاران B2B'
        ordering = ['company_name']

    def __str__(self):
        return f"{self.company_name} ({self.get_tier_display()}) - سقف اعتبار: {self.credit_limit:,}"

    @property
    def available_credit(self):
        return max(Decimal('0'), self.credit_limit - self.current_debt)


class VolumeTierDiscount(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='volume_tiers', verbose_name="تنوع کالا")
    min_quantity = models.PositiveIntegerField(verbose_name="حداقل تیراژ (MOQ)")
    unit_price = models.DecimalField(max_digits=14, decimal_places=0, verbose_name="قیمت عمده واحد (تومان)")
    tier_label = models.CharField(max_length=100, blank=True, verbose_name="عنوان سطح خرید عمده")

    class Meta:
        verbose_name = 'پلکان تخفیف حجمی و MOQ'
        verbose_name_plural = 'پلکان تخفیفات حجمی و MOQ'
        ordering = ['variant', 'min_quantity']

    def __str__(self):
        return f"{self.variant.sku} >= {self.min_quantity} عدد: {self.unit_price:,} تومان"


class POSTerminal(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, verbose_name="نام پایانه صندوق")
    terminal_code = models.CharField(max_length=50, verbose_name="کد دستگاه یا پوز")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True, blank=True, related_name='pos_terminals', verbose_name="انبار متصل به صندوق")
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    class Meta:
        verbose_name = 'صندوق حضوری (POS)'
        verbose_name_plural = 'صندوق‌های حضوری (POS)'

    def __str__(self):
        return f"{self.name} ({self.terminal_code})"


class POSSessionStatus(models.TextChoices):
    OPEN = 'OPEN', 'شیفت باز'
    CLOSED = 'CLOSED', 'شیفت بسته'


class POSRegisterSession(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    terminal = models.ForeignKey(POSTerminal, on_delete=models.CASCADE, related_name='sessions', verbose_name="صندوق")
    opened_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='pos_sessions_opened', verbose_name="کاربر گشایش")
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='pos_sessions_closed', verbose_name="کاربر بستن شیفت")
    opening_cash = models.DecimalField(max_digits=14, decimal_places=0, default=Decimal('0'), verbose_name="موجودی نقدی ابتدای شیفت")
    closing_cash = models.DecimalField(max_digits=14, decimal_places=0, null=True, blank=True, verbose_name="موجودی نقدی پایان شیفت")
    total_sales = models.DecimalField(max_digits=14, decimal_places=0, default=Decimal('0'), verbose_name="کل فروش شیفت")
    status = models.CharField(max_length=20, choices=POSSessionStatus.choices, default=POSSessionStatus.OPEN, verbose_name="وضعیت شیفت")
    opened_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان بازگشایی")
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان بستن")
    notes = models.TextField(blank=True, verbose_name="یادداشت‌های کسری یا اضافه صندوق")

    class Meta:
        verbose_name = 'شیفت صندوقداری'
        verbose_name_plural = 'شیفت‌های صندوقداری'
        ordering = ['-opened_at']

    def __str__(self):
        return f"{self.terminal.name} - {self.get_status_display()} ({self.opened_at.strftime('%Y-%m-%d %H:%M')})"


class ProformaStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'پیش‌نویس'
    SENT = 'SENT', 'ارسال‌شده به مشتری'
    ACCEPTED = 'ACCEPTED', 'تأییدشده و آماده سفارش'
    REJECTED = 'REJECTED', 'رد شده'
    CONVERTED = 'CONVERTED', 'تبدیل به سفارش نهایی'


class ProformaInvoice(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice_number = models.CharField(max_length=50, verbose_name="شماره پیش‌فاکتور")
    client = models.ForeignKey(B2BClientProfile, on_delete=models.CASCADE, related_name='proformas', verbose_name="مشتری عمده")
    subtotal = models.DecimalField(max_digits=14, decimal_places=0, default=Decimal('0'), verbose_name="جمع قبل از تخفیف")
    discount = models.DecimalField(max_digits=14, decimal_places=0, default=Decimal('0'), verbose_name="تخفیف ویژه همکاری")
    tax = models.DecimalField(max_digits=14, decimal_places=0, default=Decimal('0'), verbose_name="مالیات بر ارزش افزوده")
    grand_total = models.DecimalField(max_digits=14, decimal_places=0, default=Decimal('0'), verbose_name="مبلغ نهایی (تومان)")
    status = models.CharField(max_length=20, choices=ProformaStatus.choices, default=ProformaStatus.DRAFT, verbose_name="وضعیت")
    valid_until = models.DateTimeField(verbose_name="مهلت اعتبار")
    items = models.JSONField(default=list, verbose_name="اقلام پیش‌فاکتور (variant_id, qty, unit_price, total)")
    notes = models.TextField(blank=True, verbose_name="شرایط تحویل و تسویه")

    class Meta:
        verbose_name = 'پیش‌فاکتور رسمی B2B'
        verbose_name_plural = 'پیش‌فاکتورهای رسمی B2B'
        ordering = ['-created_at']

    def __str__(self):
        return f"پیش‌فاکتور {self.invoice_number} - {self.client.company_name} ({self.grand_total:,} تومان)"
