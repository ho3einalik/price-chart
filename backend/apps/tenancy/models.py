import uuid
from django.db import models
from django.conf import settings

class Role(models.TextChoices):
    OWNER = 'OWNER', 'مالک'
    ADMIN = 'ADMIN', 'مدیر سیستم'
    BUSINESS_MANAGER = 'BUSINESS_MANAGER', 'مدیر کسب‌وکار'
    SOCIAL_MEDIA_MANAGER = 'SOCIAL_MEDIA_MANAGER', 'مدیر شبکه‌های اجتماعی'
    CONTENT_CREATOR = 'CONTENT_CREATOR', 'تولیدکننده محتوا'
    OPS_MANAGER = 'OPS_MANAGER', 'مدیر عملیات و سفارشات'
    INVENTORY_MANAGER = 'INVENTORY_MANAGER', 'مدیر انبار'
    FULFILLMENT_STAFF = 'FULFILLMENT_STAFF', 'کارشناس ارسال و بسته‌بندی'
    SUPPORT = 'SUPPORT', 'پشتیبانی مشتریان'
    READ_ONLY = 'READ_ONLY', 'فقط خواندنی'
    CUSTOM = 'CUSTOM', 'نقش سفارشی'

class MembershipStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'فعال'
    SUSPENDED = 'SUSPENDED', 'معلق'

class InvitationStatus(models.TextChoices):
    PENDING = 'PENDING', 'در انتظار پذیرش'
    ACCEPTED = 'ACCEPTED', 'پذیرفته شده'
    REVOKED = 'REVOKED', 'لغو شده'
    EXPIRED = 'EXPIRED', 'منقضی شده'

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
    status = models.CharField(max_length=20, choices=MembershipStatus.choices, default=MembershipStatus.ACTIVE, verbose_name="وضعیت عضویت")
    is_active = models.BooleanField(default=True, verbose_name="وضعیت فعال")
    custom_permissions = models.JSONField(default=list, blank=True, verbose_name="دسترسی‌های سفارشی")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('store', 'user')
        verbose_name = 'عضویت فروشگاه'
        verbose_name_plural = 'عضویت‌های فروشگاه'

    def __str__(self):
        return f"{self.user} -> {self.store} ({self.get_role_display()})"

class TeamInvitation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='invitations')
    email = models.EmailField(verbose_name="ایمیل دعوت‌شونده")
    role = models.CharField(max_length=30, choices=Role.choices, default=Role.CONTENT_CREATOR, verbose_name="نقش پیشنهادی")
    inviter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_invitations')
    token = models.CharField(max_length=100, unique=True, db_index=True)
    status = models.CharField(max_length=20, choices=InvitationStatus.choices, default=InvitationStatus.PENDING, verbose_name="وضعیت دعوت‌نامه")
    custom_permissions = models.JSONField(default=list, blank=True, verbose_name="دسترسی‌های سفارشی")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(verbose_name="تاریخ انقضا")

    class Meta:
        verbose_name = 'دعوت‌نامه تیم'
        verbose_name_plural = 'دعوت‌نامه‌های تیم'
        ordering = ['-created_at']

    def __str__(self):
        return f"Invite to {self.email} for {self.store.name} ({self.role})"


class TenantScopedModel(models.Model):
    """Abstract model enforcing store-level isolation on every tenant record"""
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='%(class)ss')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
