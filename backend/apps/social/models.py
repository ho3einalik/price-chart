import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from apps.tenancy.models import TenantScopedModel


class SocialPlatform(models.TextChoices):
    INSTAGRAM = 'INSTAGRAM', 'اینستاگرام'
    TELEGRAM = 'TELEGRAM', 'تلگرام'
    RUBIKA = 'RUBIKA', 'روبیکا'
    BALE = 'BALE', 'بله'
    OTHER = 'OTHER', 'سایر'


class ConnectionMode(models.TextChoices):
    MANUAL_TRACKING = 'MANUAL_TRACKING', 'پیگیری دستی (بدون API مستقیم)'
    DIRECT_API = 'DIRECT_API', 'اتصال مستقیم API'


class SocialAccount(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    platform = models.CharField(
        max_length=30,
        choices=SocialPlatform.choices,
        default=SocialPlatform.INSTAGRAM,
        verbose_name="پلتفرم"
    )
    handle = models.CharField(max_length=100, verbose_name="شناسه یا آیدی کاربری (مثلاً @username)")
    display_name = models.CharField(max_length=150, blank=True, verbose_name="نام نمایشی")
    profile_image_url = models.CharField(max_length=500, blank=True, verbose_name="آدرس تصویر پروفایل")
    is_connected = models.BooleanField(default=False, verbose_name="وضعیت اتصال")
    connection_mode = models.CharField(
        max_length=30,
        choices=ConnectionMode.choices,
        default=ConnectionMode.MANUAL_TRACKING,
        verbose_name="شیوه اتصال"
    )
    follower_count = models.PositiveIntegerField(default=0, verbose_name="تعداد دنبال‌کنندگان")
    bio = models.TextField(blank=True, verbose_name="بیوگرافی")

    class Meta:
        verbose_name = "اکانت شبکه اجتماعی"
        verbose_name_plural = "اکانت‌های شبکه‌های اجتماعی"
        unique_together = ('store', 'platform', 'handle')
        ordering = ['platform', 'handle']

    def __str__(self):
        return f"{self.get_platform_display()} - {self.handle} ({self.store.name})"


class SocialCampaignObjective(models.TextChoices):
    SALES = 'SALES', 'افزایش فروش مستقیم'
    AWARENESS = 'AWARENESS', 'آگاهی از برند و معرفی'
    ENGAGEMENT = 'ENGAGEMENT', 'افزایش تعامل و فالوور'
    LEAD_GEN = 'LEAD_GEN', 'جذب مشتری راغب (لید)'


class SocialCampaignStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'پیش‌نویس'
    ACTIVE = 'ACTIVE', 'فعال / در حال اجرا'
    PAUSED = 'PAUSED', 'متوقف شده'
    COMPLETED = 'COMPLETED', 'پایان‌یافته'


class SocialCampaign(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, verbose_name="نام کمپین")
    objective = models.CharField(
        max_length=30,
        choices=SocialCampaignObjective.choices,
        default=SocialCampaignObjective.SALES,
        verbose_name="هدف کمپین"
    )
    budget = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        default=0,
        verbose_name="بودجه کمپین (تومان)"
    )
    start_date = models.DateField(null=True, blank=True, verbose_name="تاریخ شروع")
    end_date = models.DateField(null=True, blank=True, verbose_name="تاریخ پایان")
    status = models.CharField(
        max_length=30,
        choices=SocialCampaignStatus.choices,
        default=SocialCampaignStatus.DRAFT,
        verbose_name="وضعیت کمپین"
    )
    description = models.TextField(blank=True, verbose_name="توضیحات و استراتژی کمپین")

    class Meta:
        verbose_name = "کمپین شبکه‌های اجتماعی"
        verbose_name_plural = "کمپین‌های شبکه‌های اجتماعی"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"


class ContentType(models.TextChoices):
    POST = 'POST', 'پست تک‌اسلایدی'
    REEL = 'REEL', 'ریلز'
    STORY = 'STORY', 'استوری'
    CAROUSEL = 'CAROUSEL', 'پست آلبومی / اسلایدی'
    TELEGRAM_POST = 'TELEGRAM_POST', 'پست تلگرام'


class ContentStatus(models.TextChoices):
    IDEA = 'IDEA', 'ایده اولیه'
    IN_PRODUCTION = 'IN_PRODUCTION', 'در حال تولید'
    READY_FOR_REVIEW = 'READY_FOR_REVIEW', 'در انتظار بازبینی و تأیید'
    APPROVED = 'APPROVED', 'تأیید شده'
    SCHEDULED = 'SCHEDULED', 'زمان‌بندی شده برای انتشار'
    PENDING_PROOF_VERIFICATION = 'PENDING_PROOF_VERIFICATION', 'در انتظار بررسی مدرک انتشار'
    PUBLISHED = 'PUBLISHED', 'منتشر شده'
    REJECTED = 'REJECTED', 'رد شده / نیازمند اصلاح'
    ARCHIVED = 'ARCHIVED', 'بایگانی شده'



class PublishingMode(models.TextChoices):
    MANUAL_REMINDER = 'MANUAL_REMINDER', 'یادآوری انتشار دستی به ادمین'
    DIRECT_API = 'DIRECT_API', 'انتشار خودکار از طریق API'


class SocialContent(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(
        SocialAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contents',
        verbose_name="اکانت انتشار"
    )
    campaign = models.ForeignKey(
        SocialCampaign,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contents',
        verbose_name="کمپین مرتبط"
    )
    content_type = models.CharField(
        max_length=30,
        choices=ContentType.choices,
        default=ContentType.POST,
        verbose_name="نوع قالب محتوا"
    )
    title = models.CharField(max_length=255, verbose_name="عنوان موضوعی محتوا")
    caption = models.TextField(blank=True, verbose_name="کپشن یا متن پیام")
    hashtags = models.TextField(blank=True, verbose_name="هشتگ‌ها")
    media_urls = models.JSONField(default=list, blank=True, verbose_name="فایل‌ها و رسانه‌ها")
    thumbnail_url = models.CharField(max_length=500, blank=True, verbose_name="تصویر پیش‌نمایش / کاور")
    status = models.CharField(
        max_length=30,
        choices=ContentStatus.choices,
        default=ContentStatus.IDEA,
        db_index=True,
        verbose_name="وضعیت محتوا"
    )
    publishing_mode = models.CharField(
        max_length=30,
        choices=PublishingMode.choices,
        default=PublishingMode.MANUAL_REMINDER,
        verbose_name="شیوه انتشار"
    )

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_social_contents',
        verbose_name="ایجادکننده"
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_social_contents',
        verbose_name="مسئول تولید / ادیتور"
    )

    scheduled_at = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name="زمان مقرر انتشار")
    published_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان واقعی انتشار")
    published_url = models.CharField(max_length=500, blank=True, verbose_name="لینک مستقیم پست منتشر شده")
    external_post_id = models.CharField(max_length=150, blank=True, verbose_name="شناسه پست در پلتفرم خارجی")
    proof_url = models.CharField(max_length=500, blank=True, verbose_name="لینک مدرک انتشار")
    proof_image_url = models.CharField(max_length=500, blank=True, verbose_name="تصویر اسکرین‌شات مدرک انتشار")
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_social_contents',
        verbose_name="مدیر تأییدکننده انتشار"
    )

    related_product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='promoted_contents',
        verbose_name="محصول معرفی شده"
    )
    destination_url = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="لینک مقصد / خرید (لینک بیو یا استوری)"
    )

    class Meta:
        verbose_name = "محتوای شبکه‌های اجتماعی"
        verbose_name_plural = "محتواهای شبکه‌های اجتماعی"
        ordering = ['-scheduled_at', '-created_at']

    def __str__(self):
        return f"[{self.get_content_type_display()}] {self.title} ({self.get_status_display()})"


class ApprovalAction(models.TextChoices):
    SUBMITTED = 'SUBMITTED', 'ارسال جهت بررسی'
    APPROVED = 'APPROVED', 'تأیید شده'
    CHANGES_REQUESTED = 'CHANGES_REQUESTED', 'درخواست اصلاحات'
    REJECTED = 'REJECTED', 'رد شده'


class ContentApprovalLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.ForeignKey(
        SocialContent,
        on_delete=models.CASCADE,
        related_name='approval_logs',
        verbose_name="محتوا"
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviewed_social_contents',
        verbose_name="بررسی‌کننده"
    )
    action = models.CharField(
        max_length=30,
        choices=ApprovalAction.choices,
        verbose_name="عملیات بررسی"
    )
    feedback = models.TextField(blank=True, verbose_name="بازخورد / دلایل")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "گزارش بازبینی محتوا"
        verbose_name_plural = "گزارش‌های بازبینی محتوا"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_action_display()} by {self.reviewer} on {self.content.title}"


class MetricSource(models.TextChoices):
    MANUAL = 'MANUAL', 'ثبت دستی توسط ادمین'
    API = 'API', 'همگام‌سازی خودکار از اینستاگرام/شبکه'


class ContentMetricSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.ForeignKey(
        SocialContent,
        on_delete=models.CASCADE,
        related_name='metric_snapshots',
        verbose_name="محتوا"
    )
    source = models.CharField(
        max_length=20,
        choices=MetricSource.choices,
        default=MetricSource.MANUAL,
        verbose_name="منبع آمار"
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="کاربر ثبت‌کننده آمار"
    )
    reach = models.PositiveIntegerField(default=0, verbose_name="بازدید یکتا (Reach)")
    impressions = models.PositiveIntegerField(default=0, verbose_name="کل دفعات نمایش (Impressions)")
    likes = models.PositiveIntegerField(default=0, verbose_name="لایک‌ها")
    comments = models.PositiveIntegerField(default=0, verbose_name="کامنت‌ها")
    shares = models.PositiveIntegerField(default=0, verbose_name="ارسال‌ها (Share)")
    saves = models.PositiveIntegerField(default=0, verbose_name="ذخیره‌ها (Save)")
    clicks = models.PositiveIntegerField(default=0, verbose_name="کلیک‌های لینک / پروفایل")
    
    engagement_rate = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="نرخ تعامل (درصد)"
    )
    
    attributed_orders_count = models.PositiveIntegerField(
        default=0,
        verbose_name="تعداد سفارشات نسبت‌داده‌شده"
    )
    attributed_revenue = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        default=Decimal("0"),
        verbose_name="درآمد ریالی/تومانی نسبت‌داده‌شده"
    )
    recorded_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان ثبت")

    class Meta:
        verbose_name = "آمار عملکرد محتوا"
        verbose_name_plural = "آمارهای عملکرد محتوا"
        ordering = ['-recorded_at']

    def save(self, *args, **kwargs):
        # Calculate engagement rate: ((likes + comments + shares + saves) / reach) * 100
        total_interactions = self.likes + self.comments + self.shares + self.saves
        if self.reach > 0:
            rate = (Decimal(total_interactions) / Decimal(self.reach)) * Decimal(100)
            self.engagement_rate = round(rate, 2)
        else:
            self.engagement_rate = Decimal("0.00")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Metrics for {self.content.title}: Reach={self.reach}, ER={self.engagement_rate}%"
