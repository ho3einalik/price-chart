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
