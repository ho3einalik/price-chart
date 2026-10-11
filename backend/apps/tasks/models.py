import uuid
from django.db import models
from django.conf import settings
from apps.tenancy.models import TenantScopedModel


class TaskCategory(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, verbose_name="نام دسته‌بندی")
    color = models.CharField(max_length=20, default="#3B82F6", verbose_name="رنگ نشانگر")
    icon = models.CharField(max_length=50, default="check-square", verbose_name="آیکون")

    class Meta:
        verbose_name = "دسته‌بندی وظیفه"
        verbose_name_plural = "دسته‌بندی‌های وظایف"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.store.name})"


class TaskPriority(models.TextChoices):
    LOW = 'LOW', 'پایین'
    MEDIUM = 'MEDIUM', 'متوسط'
    HIGH = 'HIGH', 'بالا'
    URGENT = 'URGENT', 'فوری / اضطراری'


class TaskStatus(models.TextChoices):
    BACKLOG = 'BACKLOG', 'بک‌لاگ'
    TODO = 'TODO', 'در انتظار انجام'
    IN_PROGRESS = 'IN_PROGRESS', 'در حال انجام'
    IN_REVIEW = 'IN_REVIEW', 'در انتظار بازبینی و تأیید'
    COMPLETED = 'COMPLETED', 'تکمیل شده'
    CANCELLED = 'CANCELLED', 'لغو شده'


class Task(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, verbose_name="عنوان وظیفه")
    description = models.TextField(blank=True, verbose_name="توضیحات و دستورالعمل")
    
    category = models.ForeignKey(
        TaskCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tasks',
        verbose_name="دسته‌بندی"
    )
    priority = models.CharField(
        max_length=20,
        choices=TaskPriority.choices,
        default=TaskPriority.MEDIUM,
        verbose_name="اولویت"
    )
    status = models.CharField(
        max_length=20,
        choices=TaskStatus.choices,
        default=TaskStatus.TODO,
        db_index=True,
        verbose_name="وضعیت"
    )
    
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_tasks',
        verbose_name="ایجادکننده"
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tasks',
        verbose_name="مسئول انجام"
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_tasks',
        verbose_name="بازبین / تاییدکننده"
    )

    start_date = models.DateField(null=True, blank=True, verbose_name="تاریخ شروع")
    due_date = models.DateField(null=True, blank=True, db_index=True, verbose_name="مهلت انجام")
    
    estimated_hours = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        default=0.0,
        verbose_name="ساعت برآوردی"
    )
    actual_hours = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        default=0.0,
        verbose_name="ساعت واقعی صرف‌شده"
    )

    requires_verification = models.BooleanField(
        default=False,
        verbose_name="نیازمند بازبینی و تأیید ناظر"
    )
    completion_evidence = models.TextField(
        blank=True,
        verbose_name="شواهد و مستندات تکمیل (لینک یا یادداشت)"
    )

    related_product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='related_tasks',
        verbose_name="محصول مرتبط"
    )
    related_order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='related_tasks',
        verbose_name="سفارش مرتبط"
    )

    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان تکمیل")

    class Meta:
        verbose_name = "وظیفه"
        verbose_name_plural = "وظایف"
        ordering = ['due_date', '-created_at']

    def __str__(self):
        return f"[{self.get_priority_display()}] {self.title} ({self.get_status_display()})"


class TaskChecklistItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='checklist_items')
    title = models.CharField(max_length=255, verbose_name="عنوان چک‌لیست")
    is_completed = models.BooleanField(default=False, verbose_name="تکمیل شده")
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='completed_checklist_items'
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0, verbose_name="ترتیب نمایش")

    class Meta:
        verbose_name = "مورد چک‌لیست وظیفه"
        verbose_name_plural = "موارد چک‌لیست وظایف"
        ordering = ['order', 'title']

    def __str__(self):
        return f"{self.title} ({'تکمیل' if self.is_completed else 'در انتظار'})"


class TaskComment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='task_comments',
        verbose_name="نویسنده"
    )
    content = models.TextField(verbose_name="متن نظر")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "نظر وظیفه"
        verbose_name_plural = "نظرات وظایف"
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.author} on {self.task.title}"


class TaskActivityLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='activity_logs')
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='task_actions',
        verbose_name="انجام‌دهنده"
    )
    action_type = models.CharField(max_length=50, verbose_name="نوع عملیات")
    old_value = models.CharField(max_length=255, blank=True, verbose_name="مقدار قبلی")
    new_value = models.CharField(max_length=255, blank=True, verbose_name="مقدار جدید")
    note = models.TextField(blank=True, verbose_name="یادداشت یا توضیحات")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "گزارش فعالیت وظیفه"
        verbose_name_plural = "گزارش‌های فعالیت وظایف"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action_type} on {self.task.title} at {self.created_at}"
