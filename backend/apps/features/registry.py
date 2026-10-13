from dataclasses import dataclass, field
from typing import List, Dict, Optional
from .models import SubscriptionTier


class CircularDependencyError(Exception):
    """Raised when circular dependencies are detected in the feature registry"""
    pass


@dataclass
class FeatureDefinition:
    key: str
    name_fa: str
    description_fa: str
    category: str  # CORE, OPERATIONS, TEAM, SOCIAL, MARKETING, AI, ANALYTICS
    is_core: bool = False
    default_enabled: bool = True
    min_tier: str = SubscriptionTier.FREE
    depends_on: List[str] = field(default_factory=list)
    required_integrations: List[str] = field(default_factory=list)
    impact_warning_fa: str = ""


# Central Feature Registry
FEATURE_CATALOG: Dict[str, FeatureDefinition] = {
    # Core Domain Features (Always enabled and entitled on all plans)
    'core.catalog': FeatureDefinition(
        key='core.catalog',
        name_fa='کاتالوگ کالاها و تنوع‌ها',
        description_fa='مدیریت دسته‌بندی‌ها، محصولات و قیمت‌گذاری کالاها',
        category='CORE',
        is_core=True,
        default_enabled=True,
        min_tier=SubscriptionTier.FREE
    ),
    'core.orders': FeatureDefinition(
        key='core.orders',
        name_fa='مدیریت سفارشات و صدور فاکتور',
        description_fa='ثبت سفارش، محاسبه مالیات و تخفیف و ردیابی وضعیت سفارشات',
        category='CORE',
        is_core=True,
        default_enabled=True,
        min_tier=SubscriptionTier.FREE
    ),
    'core.inventory': FeatureDefinition(
        key='core.inventory',
        name_fa='انبارداری و موجودی کالا',
        description_fa='دفترکل دوبل موجودی و ردیابی رزروها و جابجایی کالا بین انبارها',
        category='OPERATIONS',
        is_core=True,
        default_enabled=True,
        min_tier=SubscriptionTier.FREE
    ),
    'core.payments': FeatureDefinition(
        key='core.payments',
        name_fa='تأیید فیش بانکی و درگاه پرداخت',
        description_fa='تأیید تراکنش‌های کارت‌به‌کارت و درگاه‌های بانکی متصل',
        category='OPERATIONS',
        is_core=True,
        default_enabled=True,
        min_tier=SubscriptionTier.FREE
    ),

    # Team & RBAC
    'team.management': FeatureDefinition(
        key='team.management',
        name_fa='مدیریت تیم و سطوح دسترسی (RBAC)',
        description_fa='تعریف همکاران، نقش‌های سازمانی و تعیین مجوزهای اختصاصی',
        category='TEAM',
        is_core=False,
        default_enabled=True,
        min_tier=SubscriptionTier.STARTER,
        impact_warning_fa='با غیرفعال‌سازی این بخش، دسترسی سایر همکاران به این فروشگاه موقتاً محدود شده و فقط مالک دسترسی خواهد داشت.'
    ),

    # Tasks & Operations Engine
    'tasks.planner': FeatureDefinition(
        key='tasks.planner',
        name_fa='کارتابل وظایف و بورد کانبان',
        description_fa='مدیریت کارهای روزمره انبار، بسته‌بندی، محتوا همراه با چک‌لیست و تأیید ناظر',
        category='OPERATIONS',
        is_core=False,
        default_enabled=True,
        min_tier=SubscriptionTier.STARTER,
        impact_warning_fa='با غیرفعال‌سازی، وظایف فعلی حفظ می‌شوند اما اعضای تیم به کارتابل وظایف دسترسی نخواهند داشت.'
    ),
    'tasks.recurring': FeatureDefinition(
        key='tasks.recurring',
        name_fa='وظایف دوره‌ای و خودکار',
        description_fa='تولید خودکار وظایف هفتگی یا ماهانه مانند انبارگردانی و فاکتورها',
        category='OPERATIONS',
        is_core=False,
        default_enabled=False,
        min_tier=SubscriptionTier.PRO,
        depends_on=['tasks.planner'],
        impact_warning_fa='وظایف دوره‌ای متوقف خواهند شد.'
    ),

    # Social Media Operations & Planner
    'social.content_calendar': FeatureDefinition(
        key='social.content_calendar',
        name_fa='تقویم بصری محتوا و انتشار',
        description_fa='برنامه‌ریزی زمانی ریلزها، استوری‌ها و پست‌های اینستاگرام و تلگرام',
        category='SOCIAL',
        is_core=False,
        default_enabled=True,
        min_tier=SubscriptionTier.STARTER,
        impact_warning_fa='تقویم محتوا موقتاً از دسترس خارج می‌شود. داده‌های محتواهای قبلی حفظ خواهند شد.'
    ),
    'social.content_approval': FeatureDefinition(
        key='social.content_approval',
        name_fa='کارتابل تایید و بازبینی محتوا',
        description_fa='فرآیند داوری محتوا پیش از انتشار و تبادل نظر بین مدیر و ادیتور',
        category='SOCIAL',
        is_core=False,
        default_enabled=True,
        min_tier=SubscriptionTier.STARTER,
        depends_on=['social.content_calendar'],
        impact_warning_fa='تایید قبل از انتشار غیرفعال شده و محتواها بدون بازبینی منتشر یا زمان‌بندی می‌شوند.'
    ),
    'social.auto_publish': FeatureDefinition(
        key='social.auto_publish',
        name_fa='انتشار خودکار از طریق API اینستاگرام',
        description_fa='ارسال خودکار ریلزها و استوری‌ها در زمان مقرر بدون نیاز به یادآوری دستی',
        category='SOCIAL',
        is_core=False,
        default_enabled=False,
        min_tier=SubscriptionTier.PRO,
        depends_on=['social.content_calendar'],
        required_integrations=['instagram'],
        impact_warning_fa='انتشار خودکار متوقف شده و سیستم به حالت یادآوری دستی تغییر وضعیت می‌دهد.'
    ),
    'social.analytics': FeatureDefinition(
        key='social.analytics',
        name_fa='آنالیز عملکرد و نرخ تعامل شبکه‌های اجتماعی',
        description_fa='محاسبه Engagement Rate بر مبنای Reach و انتساب فروش محتوا به سفارشات',
        category='SOCIAL',
        is_core=False,
        default_enabled=True,
        min_tier=SubscriptionTier.STARTER,
        impact_warning_fa='گزارشات تحلیلی شبکه‌های اجتماعی غیرفعال می‌شود. گزارشات مالی و سفارشات تحت‌الشعاع قرار نمی‌گیرند.'
    ),
    'social.ai_dm_assistant': FeatureDefinition(
        key='social.ai_dm_assistant',
        name_fa='دستیار هوشمند دایرکت و کامنت اینستاگرام',
        description_fa='پاسخگویی خودکار مبتنی بر هوش مصنوعی به سوالات موجودی، سایز و ثبت سفارش در دایرکت',
        category='AI',
        is_core=False,
        default_enabled=False,
        min_tier=SubscriptionTier.PRO,
        depends_on=['core.catalog'],
        required_integrations=['instagram', 'ai_provider'],
        impact_warning_fa='پاسخگویی خودکار دایرکت غیرفعال می‌شود. ادمین‌های انسانی باید به پیام‌ها پاسخ دهند.'
    ),

    # AI Assistants
    'ai.assistant': FeatureDefinition(
        key='ai.assistant',
        name_fa='دستیار هوشمند نگارش و تولید محتوا',
        description_fa='نگارش خودکار کپشن اینستاگرام، توضیحات تخصصی کالاها و متن‌های بازاریابی',
        category='AI',
        is_core=False,
        default_enabled=True,
        min_tier=SubscriptionTier.STARTER,
        required_integrations=['ai_provider'],
        impact_warning_fa='پیشنهادات هوش مصنوعی غیرفعال می‌شود اما تولید محتوای دستی و عملیات عادی کالاها بدون وقفه فعال خواهند بود.'
    ),

    # Marketing & Loyalty
    'marketing.loyalty': FeatureDefinition(
        key='marketing.loyalty',
        name_fa='باشگاه مشتریان و سطوح وفاداری (VIP)',
        description_fa='امتیازدهی به خریدهای مشتری، سطوح تخفیف پلکانی و کدهای هدیه سالگرد خرید',
        category='MARKETING',
        is_core=False,
        default_enabled=False,
        min_tier=SubscriptionTier.PRO,
        depends_on=['core.orders'],
        impact_warning_fa='محاسبه امتیازات جدید موقتاً متوقف می‌شود. سوابق قبلی مشتریان و پروفایل‌ها دست‌نخورده باقی می‌مانند.'
    ),

    # Advanced Analytics & Forecasting
    'analytics.forecasting': FeatureDefinition(
        key='analytics.forecasting',
        name_fa='پیش‌بینی هوشمند تقاضا و نقطه سفارش مجدد',
        description_fa='تخمین زمان اتمام موجودی و پیشنهاد میزان خرید کالا بر مبنای روند فروش فصلی',
        category='ANALYTICS',
        is_core=False,
        default_enabled=False,
        min_tier=SubscriptionTier.ENTERPRISE,
        depends_on=['core.inventory', 'core.orders'],
        impact_warning_fa='پیش‌بینی‌های هوشمند غیرفعال می‌شوند. ثبت عادی اسناد انبار و سفارشات فعال خواهد ماند.'
    ),
    'competitors.intelligence': FeatureDefinition(
        key='competitors.intelligence',
        name_fa='رصد هوشمند قیمت و رقبا',
        description_fa='پایش تغییرات قیمت کالاهای مشابه در بازار و اعلان فرصت‌های رقابتی',
        category='ANALYTICS',
        is_core=False,
        default_enabled=False,
        min_tier=SubscriptionTier.ENTERPRISE,
        depends_on=['core.catalog'],
        impact_warning_fa='رصد رقبا متوقف می‌شود.'
    ),
    'suppliers.management': FeatureDefinition(
        key='suppliers.management',
        name_fa='مدیریت تأمین‌کنندگان و سفارشات خرید (PO)',
        description_fa='ثبت سفارشات خرید، رهگیری ورود کالا و بدهی تأمین‌کنندگان',
        category='OPERATIONS',
        is_core=False,
        default_enabled=True,
        min_tier=SubscriptionTier.STARTER,
        depends_on=['core.inventory']
    ),
    'wholesale_pos.cashier': FeatureDefinition(
        key='wholesale_pos.cashier',
        name_fa='صندوق فروش حضوری و عمده‌فروشی',
        description_fa='فروش سریع، فاکتور عمده و محاسبه فوری اعتبار مشتریان B2B',
        category='OPERATIONS',
        is_core=False,
        default_enabled=True,
        min_tier=SubscriptionTier.STARTER,
        depends_on=['core.orders', 'core.inventory']
    ),
    'marketing.abandoned_carts': FeatureDefinition(
        key='marketing.abandoned_carts',
        name_fa='بازیابی سبدهای خرید رهاشده',
        description_fa='رهگیری سبدهای خرید رها شده و ارسال خودکار پیامک یادآوری',
        category='MARKETING',
        is_core=False,
        default_enabled=True,
        min_tier=SubscriptionTier.STARTER,
        depends_on=['core.orders']
    ),
    'crm.customer_profiles': FeatureDefinition(
        key='crm.customer_profiles',
        name_fa='پروفایل ۳۶۰ درجه و مدیریت ارتباط با مشتریان (CRM)',
        description_fa='بخش‌بندی RFM، یادداشت‌ها و تاریخچه تعاملات با مشتریان',
        category='MARKETING',
        is_core=False,
        default_enabled=True,
        min_tier=SubscriptionTier.STARTER,
        depends_on=['core.orders']
    ),
    'automation.rules': FeatureDefinition(
        key='automation.rules',
        name_fa='موتور اتوماسیون و گردش کار خودکار',
        description_fa='ایجاد قوانین خودکار بر مبنای رویدادها، ارسال پیامک و تعریف وظایف',
        category='OPERATIONS',
        is_core=False,
        default_enabled=True,
        min_tier=SubscriptionTier.PRO
    ),
}


# Plan Entitlement Rules
TIER_HIERARCHY = {
    SubscriptionTier.FREE: 0,
    SubscriptionTier.STARTER: 1,
    SubscriptionTier.PRO: 2,
    SubscriptionTier.ENTERPRISE: 3,
}

def is_tier_sufficient(store_tier: str, required_tier: str) -> bool:
    return TIER_HIERARCHY.get(store_tier, 0) >= TIER_HIERARCHY.get(required_tier, 0)


def validate_dependency_graph(catalog: Optional[Dict[str, FeatureDefinition]] = None):
    """
    Validates that the feature dependency graph is a Directed Acyclic Graph (DAG).
    Raises CircularDependencyError if any cycle is found.
    """
    cat = catalog or FEATURE_CATALOG
    visited = {}  # key -> 'visiting' or 'visited'

    def dfs(node: str, path: List[str]):
        state = visited.get(node)
        if state == 'visiting':
            cycle = path[path.index(node):] + [node]
            raise CircularDependencyError(
                f"چرخه وابستگی نامعتبر شناسایی شد: {' -> '.join(cycle)}"
            )
        if state == 'visited':
            return

        visited[node] = 'visiting'
        feat = cat.get(node)
        if feat:
            for dep in feat.depends_on:
                if dep in cat:
                    dfs(dep, path + [dep])

        visited[node] = 'visited'

    for feat_key in cat:
        if feat_key not in visited:
            dfs(feat_key, [feat_key])

    return True


# Run DAG validation on module import
validate_dependency_graph()


def get_all_features() -> List[FeatureDefinition]:
    return list(FEATURE_CATALOG.values())


def get_feature(key: str) -> Optional[FeatureDefinition]:
    return FEATURE_CATALOG.get(key)


def get_dependent_features(feature_key: str) -> List[FeatureDefinition]:
    """Finds all features that directly or indirectly depend on this feature"""
    dependents = []
    for f in FEATURE_CATALOG.values():
        if feature_key in f.depends_on:
            dependents.append(f)
    return dependents
