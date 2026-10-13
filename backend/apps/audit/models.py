import uuid
from django.db import models
from django.conf import settings
from apps.tenancy.models import Store

class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, null=True, blank=True, related_name='audit_logs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=100, db_index=True, verbose_name="عملیات")
    target_type = models.CharField(max_length=100, db_index=True, verbose_name="نوع موجودیت")
    target_id = models.CharField(max_length=100, db_index=True, verbose_name="شناسه موجودیت")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    changes = models.JSONField(default=dict, blank=True, verbose_name="جزئیات تغییرات")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="زمان ثبت")

    class Meta:
        verbose_name = 'گزارش حسابرسی'
        verbose_name_plural = 'گزارش‌های حسابرسی'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action} by {self.user or 'System'} on {self.target_type}:{self.target_id}"


class NotificationCategory(models.TextChoices):
    ORDER = 'ORDER', 'سفارشات'
    INVENTORY = 'INVENTORY', 'انبار و موجودی'
    PAYMENT = 'PAYMENT', 'امور مالی و پرداخت'
    SOCIAL = 'SOCIAL', 'شبکه‌های اجتماعی و پیام‌ها'
    SYSTEM = 'SYSTEM', 'سیستمی و امنیتی'


class NotificationLevel(models.TextChoices):
    INFO = 'INFO', 'اطلاع‌رسانی'
    SUCCESS = 'SUCCESS', 'موفقیت'
    WARNING = 'WARNING', 'هشدار'
    ERROR = 'ERROR', 'خطا و اضطراری'


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='notifications')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications', verbose_name="کاربر گیرنده (خالی = کل تیم)")
    title = models.CharField(max_length=200, verbose_name="عنوان اعلان")
    message = models.TextField(verbose_name="متن اعلان")
    category = models.CharField(max_length=30, choices=NotificationCategory.choices, default=NotificationCategory.SYSTEM, verbose_name="دسته‌بندی")
    level = models.CharField(max_length=20, choices=NotificationLevel.choices, default=NotificationLevel.INFO, verbose_name="سطح اهمیت")
    is_read = models.BooleanField(default=False, db_index=True, verbose_name="خوانده شده")
    action_url = models.CharField(max_length=500, blank=True, verbose_name="لینک اقدام")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="زمان ایجاد")

    class Meta:
        verbose_name = 'اعلان درون‌برنامه‌ای'
        verbose_name_plural = 'اعلان‌های درون‌برنامه‌ای'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_level_display()}] {self.title}"


class NotificationPreference(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_preferences')
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='user_notification_preferences')
    order_alerts = models.BooleanField(default=True, verbose_name="هشدارهای ثبت و لغو سفارش")
    inventory_low_stock = models.BooleanField(default=True, verbose_name="هشدارهای کسری موجودی کالا")
    payment_alerts = models.BooleanField(default=True, verbose_name="هشدارهای دریافت و تایید فیش واریزی")
    social_messages = models.BooleanField(default=True, verbose_name="پیام‌های جدید شبکه‌های اجتماعی")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'store')
        verbose_name = 'تنظیمات دریافت اعلان‌ها'
        verbose_name_plural = 'تنظیمات دریافت اعلان‌ها'

    def __str__(self):
        return f"Preferences of {self.user.email or self.user.full_name} for {self.store.name}"
