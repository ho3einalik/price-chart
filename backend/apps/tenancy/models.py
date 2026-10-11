import uuid
from django.db import models
from django.conf import settings

class Role(models.TextChoices):
    OWNER = 'OWNER', 'مالک'
    ADMIN = 'ADMIN', 'مدیر سیستم'
    OPS_MANAGER = 'OPS_MANAGER', 'مدیر عملیات'
    INVENTORY_MANAGER = 'INVENTORY_MANAGER', 'مدیر انبار'
    FULFILLMENT_STAFF = 'FULFILLMENT_STAFF', 'کارشناس ارسال و بسته‌بندی'
    SUPPORT = 'SUPPORT', 'پشتیبانی مشتریان'
    READ_ONLY = 'READ_ONLY', 'فقط خواندنی'

class Business(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, verbose_name="نام کسب‌وکار")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owned_businesses')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'کسب‌وکار'
        verbose_name_plural = 'کسب‌وکارها'

    def __str__(self):
        return self.name

class Store(models.Model):
    class Currency(models.TextChoices):
        IRT = 'IRT', 'تومان (IRT)'
        IRR = 'IRR', 'ریال (IRR)'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='stores')
    name = models.CharField(max_length=200, verbose_name="نام فروشگاه")
    currency = models.CharField(max_length=10, choices=Currency.choices, default=Currency.IRT, verbose_name="واحد پولی")
    timezone = models.CharField(max_length=50, default='Asia/Tehran', verbose_name="منطقه زمانی")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'فروشگاه'
        verbose_name_plural = 'فروشگاه‌ها'

    def __str__(self):
        return f"{self.name} ({self.business.name})"

class StoreMembership(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='store_memberships')
    role = models.CharField(max_length=30, choices=Role.choices, default=Role.OWNER, verbose_name="نقش")
    is_active = models.BooleanField(default=True, verbose_name="وضعیت فعال")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('store', 'user')
        verbose_name = 'عضویت فروشگاه'
        verbose_name_plural = 'عضویت‌های فروشگاه'

    def __str__(self):
        return f"{self.user} -> {self.store} ({self.get_role_display()})"

class TenantScopedModel(models.Model):
    """Abstract model enforcing store-level isolation on every tenant record"""
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='%(class)ss')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
