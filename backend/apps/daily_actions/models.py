import uuid
from django.db import models
from django.conf import settings
from apps.tenancy.models import TenantScopedModel

class ActionSeverity(models.TextChoices):
    CRITICAL = 'CRITICAL', 'بحرانی'
    HIGH = 'HIGH', 'بالا'
    MEDIUM = 'MEDIUM', 'متوسط'
    LOW = 'LOW', 'پایین'

class ActionStatus(models.TextChoices):
    NEW = 'NEW', 'جدید'
    ACKNOWLEDGED = 'ACKNOWLEDGED', 'مشاهده شده'
    IN_PROGRESS = 'IN_PROGRESS', 'در حال پیگیری'
    RESOLVED = 'RESOLVED', 'حل شده'
    DISMISSED = 'DISMISSED', 'رد شده'

class DailyAction(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    action_key = models.CharField(max_length=100, db_index=True, verbose_name="کلید یکتای هشدار")
    title = models.CharField(max_length=255, verbose_name="عنوان اقدام")
    explanation = models.TextField(verbose_name="توضیح و علت هشدار")
    severity = models.CharField(max_length=20, choices=ActionSeverity.choices, default=ActionSeverity.MEDIUM, verbose_name="شدت اهمیت")
    status = models.CharField(max_length=30, choices=ActionStatus.choices, default=ActionStatus.NEW, verbose_name="وضعیت اقدام")
    
    suggested_action = models.CharField(max_length=255, verbose_name="اقدام پیشنهادی سیستم")
    evidence = models.JSONField(default=dict, blank=True, verbose_name="شواهد و رکوردهای مرتبط")
    
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_actions')
    resolution_note = models.TextField(blank=True, verbose_name="یادداشت خاتمه / حل مسئله")
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'اقدام روزانه'
        verbose_name_plural = 'مرکز اقدامات روزانه'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.severity}] {self.title} ({self.get_status_display()})"
