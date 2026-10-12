import uuid
from decimal import Decimal
from django.db import models
from apps.tenancy.models import TenantScopedModel
from apps.catalog.models import ProductVariant
from apps.orders.models import Customer, Order

class FeedbackCategory(models.TextChoices):
    PRODUCT_QUALITY = 'PRODUCT_QUALITY', 'کیفیت و اصالت کالا'
    SHIPPING_DELAY = 'SHIPPING_DELAY', 'تاخیر در ارسال یا آسیب پستی'
    PACKAGING = 'PACKAGING', 'بسته‌بندی و ظاهر مرسوله'
    CUSTOMER_SERVICE = 'CUSTOMER_SERVICE', 'پاسخگویی پشتیبانی و رفتار پرسنل'
    PRICING = 'PRICING', 'قیمت‌گذاری و تخفیفات'
    OTHER = 'OTHER', 'سایر موارد'


class SentimentType(models.TextChoices):
    POSITIVE = 'POSITIVE', 'مثبت و رضایت‌بخش'
    NEUTRAL = 'NEUTRAL', 'خنثی / متوسط'
    NEGATIVE = 'NEGATIVE', 'منفی / نارضایتی و شکایت'


class CustomerFeedback(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='feedbacks', verbose_name="مشتری")
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name='feedbacks', verbose_name="سفارش مرتبط")
    rating = models.PositiveSmallIntegerField(default=5, verbose_name="امتیاز رضایت (۱ تا ۵)")
    category = models.CharField(max_length=30, choices=FeedbackCategory.choices, default=FeedbackCategory.PRODUCT_QUALITY, verbose_name="دسته‌بندی موضوعی")
    sentiment = models.CharField(max_length=20, choices=SentimentType.choices, default=SentimentType.POSITIVE, verbose_name="تحلیل حس و لحن")
    comment = models.TextField(verbose_name="متن نظر یا شکایت مشتری")
    is_resolved = models.BooleanField(default=False, verbose_name="رسیدگی و حل‌وفصل شده")
    resolution_notes = models.TextField(blank=True, verbose_name="اقدام انجام‌شده جهت جلب رضایت")

    class Meta:
        verbose_name = 'بازخورد و شکایت مشتری'
        verbose_name_plural = 'بازخوردها و شکایات مشتریان'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.customer.full_name if self.customer else 'ناشناس'} ({self.get_sentiment_display()} - {self.rating} ستاره)"


class CompetitorPriceTrack(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='competitor_prices', verbose_name="کالای ما")
    competitor_name = models.CharField(max_length=150, verbose_name="نام فروشگاه رقیب (دیجی‌کالا، ترب، باسلام)")
    competitor_url = models.CharField(max_length=500, blank=True, verbose_name="لینک صفحه کالای رقیب")
    competitor_price = models.DecimalField(max_digits=14, decimal_places=0, verbose_name="قیمت رقیب (تومان)")
    price_difference_percent = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'), verbose_name="درصد اختلاف قیمت")
    last_checked_at = models.DateTimeField(auto_now=True, verbose_name="زمان آخرین بررسی")

    class Meta:
        verbose_name = 'پایش قیمت رقیب'
        verbose_name_plural = 'پایش قیمت رقبا'
        ordering = ['-last_checked_at']

    def save(self, *args, **kwargs):
        if self.variant and self.variant.retail_price > 0:
            diff = ((self.competitor_price - self.variant.retail_price) / self.variant.retail_price) * Decimal('100')
            self.price_difference_percent = round(diff, 2)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.variant.sku} vs {self.competitor_name}: {self.competitor_price:,} تومان ({self.price_difference_percent}%)"
