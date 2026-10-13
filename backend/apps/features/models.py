import uuid
from django.db import models
from django.conf import settings
from apps.tenancy.models import Store


class SubscriptionTier(models.TextChoices):
    FREE = 'FREE', 'طرح رایگان (Free)'
    STARTER = 'STARTER', 'طرح پایه و استارتر (Starter)'
    PRO = 'PRO', 'طرح حرفه‌ای (Pro)'
    ENTERPRISE = 'ENTERPRISE', 'طرح سازمانی (Enterprise)'


class IntegrationState(models.TextChoices):
    CONNECTED = 'CONNECTED', 'متصل و آماده به کار'
    CONFIGURED = 'CONFIGURED', 'پیکربندی شده'
    CONNECTION_TESTED = 'CONNECTION_TESTED', 'اتصال با موفقیت تست شده'
    NOT_CONFIGURED = 'NOT_CONFIGURED', 'پیکربندی‌نشده'
    DISABLED_BY_STORE = 'DISABLED_BY_STORE', 'غیرفعال توسط فروشگاه'
    PLAN_RESTRICTED = 'PLAN_RESTRICTED', 'نیازمند ارتقای اشتراک'
    UNAVAILABLE = 'UNAVAILABLE', 'موقتاً در دسترس نیست'
    NEEDS_REAUTH = 'NEEDS_REAUTH', 'نیازمند اتصال مجدد / انقضای توکن'
    FAILED_RECOVERY = 'FAILED_RECOVERY', 'خطای ارتباط - در انتظار بازیابی'
    ERROR = 'ERROR', 'خطای ارتباط با سرویس'
    MOCKED = 'MOCKED', 'شبیه‌سازی / حالت تستی'
    MANUAL_ONLY = 'MANUAL_ONLY', 'فقط حالت دستی'


class StoreFeatureSetting(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.OneToOneField(
        Store,
        on_delete=models.CASCADE,
        related_name='feature_settings',
        verbose_name="فروشگاه"
    )
    tier = models.CharField(
        max_length=30,
        choices=SubscriptionTier.choices,
        default=SubscriptionTier.FREE,
        verbose_name="سطح اشتراک فروشگاه"
    )
    enabled_features = models.JSONField(
        default=list,
        blank=True,
        verbose_name="ویژگی‌های صراحتاً فعال‌شده"
    )
    disabled_features = models.JSONField(
        default=list,
        blank=True,
        verbose_name="ویژگی‌های صراحتاً غیرفعال‌شده توسط کاربر"
    )
    feature_configs = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="تنظیمات اختصاصی ماژول‌ها"
    )
    integration_states = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="وضعیت اتصالات سرویس‌های خارجی"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "تنظیمات ماژول‌ها و ویژگی‌های فروشگاه"
        verbose_name_plural = "تنظیمات ماژول‌های فروشگاه‌ها"

    def __str__(self):
        return f"Feature Settings: {self.store.name} ({self.get_tier_display()})"


class InvoiceStatus(models.TextChoices):
    PENDING = 'PENDING', 'در انتظار پرداخت'
    PAID = 'PAID', 'پرداخت شده'
    FAILED = 'FAILED', 'ناموفق'
    CANCELLED = 'CANCELLED', 'لغو شده'


class SubscriptionInvoice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name='subscription_invoices',
        verbose_name="فروشگاه"
    )
    tier = models.CharField(
        max_length=30,
        choices=SubscriptionTier.choices,
        verbose_name="سطح اشتراک"
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        verbose_name="مبلغ پرداختی (تومان)"
    )
    status = models.CharField(
        max_length=20,
        choices=InvoiceStatus.choices,
        default=InvoiceStatus.PENDING,
        verbose_name="وضعیت صورتحساب"
    )
    payment_reference = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="شناسه ارجاع پرداخت"
    )
    gateway_tracking_code = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="کد رهگیری درگاه"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "صورتحساب اشتراک"
        verbose_name_plural = "صورتحساب‌های اشتراک"
        ordering = ['-created_at']

    def __str__(self):
        return f"Invoice {self.id} - {self.store.name} - {self.tier} ({self.status})"
