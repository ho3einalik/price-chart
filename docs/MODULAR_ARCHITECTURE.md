# معماری ماژولار، قابلیت‌های مستقل و تاب‌آوری سامانه شاپ‌پایلوت (ShopPilot Modular Architecture)

این مستند معماری، اصول طراحی، سیستم حق‌دسترسی و مدیریت ویژگی‌ها (Feature Entitlements & Modularity)، ساختار گراف وابستگی‌ها (DAG)، و راهکارهای تنزل برازنده (Graceful Degradation) در پلتفرم SaaS چندمستاجره **ShopPilot** را تشریح می‌کند.

---

## ۱. اصول بنیادین معماری (Core Architecture Principles)

1. **استقلال ماژول‌ها (Module Independence):**
   - هیچ ماژول اختیاری (مانند هوش مصنوعی، آنالیز اینستاگرام، باشگاه مشتریان یا کارتابل وظایف) نباید عملکرد ماژول‌های پایه (کاتالوگ، ثبت سفارش، مدیریت موجودی، پرداخت و احراز هویت) را مختل کند.
2. **جداسازی مجوزها از در دسترس بودن ماژول (Separation of Entitlement, Availability & Permissions):**
   - **حق‌دسترسی بر اساس اشتراک (Tier Entitlement):** آیا پلن فعلی فروشگاه (`FREE`, `STARTER`, `PRO`, `ENTERPRISE`) مجاز به استفاده از این قابلیت است؟
   - **پیکربندی سطح فروشگاه (Store Enablement):** آیا مالک فروشگاه این ماژول را در تنظیمات فعال کرده است؟
   - **آمادگی پیش‌نیازها (Dependency Readiness):** آیا ماژول‌های بالادستی مورد نیاز فعال هستند؟
   - **آمادگی سرویس‌های خارجی (Integration Readiness):** آیا کلیدها یا دسترسی‌های اتصال (مثل اینستاگرام یا پیامک) تنظیم شده‌اند؟
   - **دسترسی نقش کاربر (RBAC Permissions):** آیا نقش کاربر جاری در این فروشگاه (`OWNER`, `ADMIN`, `CONTENT_CREATOR`, ...) مجوز اقدام دارد؟
3. **اصل عدم حذف داده‌ها (Data Preservation Guarantee):**
   - غیرفعال‌سازی موقت یک ماژول توسط کاربر یا به دلیل تغییر پلن اشتراک، **به هیچ عنوان داده‌ها، جداول، سوابق یا کلیدهای خارجی را حذف نمی‌کند**.
   - اطلاعات دست‌نخورده باقی می‌مانند و به محض فعال‌سازی مجدد، بدون نقص قابل بهره‌برداری هستند.
4. **تنزل برازنده در سرویس‌های خارجی (Graceful Degradation & Heuristic Fallbacks):**
   - قطعی شبکه یا خطای ارائه‌دهنده خارجی (مانند Meta Graph API یا Google Gemini) هرگز باعث خطای ۵۰۰ یا مسدود شدن کارکرد سایر بخش‌ها نمی‌شود.

---

## ۲. کاتالوگ ماژول‌ها و گراف وابستگی‌ها (DAG)

| کلید ماژول | نام فارسی | دسته‌بندی | وضعیت پایه | حداقل پلن | پیش‌نیازها (`depends_on`) | آداپتور خارجی |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| `core.catalog` | کاتالوگ و محصولات | CORE | بله | FREE | ندارد | ندارد |
| `core.orders` | سفارشات و فاکتورها | CORE | بله | FREE | ندارد | ندارد |
| `core.inventory` | انبارداری و موجودی | OPERATIONS | بله | FREE | ندارد | ندارد |
| `core.payments` | پرداخت و فیش بانکی | OPERATIONS | بله | FREE | ندارد | ندارد |
| `team.management` | مدیریت تیم و RBAC | TEAM | خیر | STARTER | ندارد | ندارد |
| `tasks.planner` | کارتابل وظایف و کانبان | OPERATIONS | خیر | STARTER | ندارد | ندارد |
| `tasks.recurring` | وظایف دوره‌ای خودکار | OPERATIONS | خیر | PRO | `tasks.planner` | ندارد |
| `social.content_calendar` | تقویم بصری محتوا | SOCIAL | خیر | STARTER | ندارد | ندارد |
| `social.content_approval` | کارتابل تایید محتوا | SOCIAL | خیر | STARTER | `social.content_calendar` | ندارد |
| `social.auto_publish` | انتشار خودکار اینستاگرام | SOCIAL | خیر | PRO | `social.content_calendar` | `instagram` |
| `social.analytics` | آنالیز و اینگیجمنت | SOCIAL | خیر | STARTER | ندارد | ندارد |
| `social.ai_dm_assistant` | دستیار هوشمند دایرکت | AI | خیر | PRO | `core.catalog` | `instagram`, `ai_provider` |
| `ai.assistant` | نگارش هوشمند محتوا | AI | خیر | STARTER | ندارد | `ai_provider` |
| `marketing.loyalty` | باشگاه مشتریان و VIP | MARKETING | خیر | PRO | `core.orders` | ندارد |

### اعتبارسنجی بدون چرخه بودن گراف (Acyclic Graph Validation)
در زمان راه‌اندازی و تست‌ها، تابع `validate_dependency_graph(FEATURE_CATALOG)` ساختار گراف وابستگی‌ها را با الگوریتم DFS ارزیابی می‌کند. هرگونه وابستگی چرخه‌ای (Circular Dependency) خطای `CircularDependencyError` تولید می‌کند.

---

## ۳. لایه آداپتورهای مستقل (Integration Adapters)

برای جلوگیری از وابستگی مستقیم به ارائه‌دهندگان سرویس شخص ثالث، سه آداپتور پیاده‌سازی شده است:

1. **`InstagramIntegrationAdapter`:**
   - بررسی وضعیت توکن و اتصال پیج اینستاگرام.
   - در صورت قطع بودن اتصال (`NOT_CONFIGURED` یا `NEEDS_REAUTH`)، قابلیت ثبت دستی محتوا، زمان‌بندی و تقویم بصری بدون وقفه کار می‌کند.
2. **`AIProviderIntegrationAdapter`:**
   - مدیریت فراخوانی مدل‌های هوش مصنوعی (Gemini / OpenAI).
   - در صورت قطع بودن اتصال یا خطا در API، به صورت خودکار به **قالب‌های هوشمند محلی (Heuristic Fallback)** سوئیچ می‌کند تا تجربه کاربر هرگز متوقف نشود.
3. **`SMSGatewayIntegrationAdapter`:**
   - ارسال پیامک‌های پیگیری و تایید سفارشات.
   - پردازش به صورت امن و غیرمسدودکننده (Non-blocking) انجام شده و خطای ارسال پیامک مانع از ثبت سفارش یا پرداخت نمی‌گردد.

---

## ۴. کنترل دسترسی در API (DRF Permission Class: `RequiresFeature`)

کلاس دسترسی `RequiresFeature` بر روی کلیه اندپوینت‌های ماژولار اعمال شده است:

```python
class TaskViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission, RequiresFeature('tasks.planner')]
```

در صورتی که ماژول به هر دلیلی غیرفعال باشد، پاسخ `HTTP 403 Forbidden` با ساختار استاندارد زیر بازگردانده می‌شود:
```json
{
  "code": "FEATURE_DISABLED",
  "feature": "tasks.planner",
  "message": "ماژول 'کارتابل وظایف و بورد کانبان' توسط مالک فروشگاه غیرفعال شده است.",
  "reactivation_hint": "می‌توانید وضعیت و تنظیمات این ماژول را در بخش تنظیمات فروشگاه بررسی کنید."
}
```

کدهای خطای استاندارد:
- `PLAN_RESTRICTED`: نیازمند ارتقای پلن اشتراک.
- `FEATURE_DISABLED`: غیرفعال شده توسط مالک در تنظیمات.
- `DEPENDENCY_MISSING`: فعال نبودن ماژول‌های بالادستی.
- `INTEGRATION_NOT_READY`: عدم اتصال سرویس خارجی الزامی.
- `USER_UNAUTHORIZED`: عدم دارا بودن نقش یا مجوز کافی.

---

## ۵. رابط کاربری تنظیمات ویژگی‌ها (`/settings/features`)

رابط کاربری مدرن در مسیر `/settings/features` با مشخصات زیر فعال است:
- نمایش پلن اشتراک فعال و امکان جابجایی بین پلن‌ها جهت تست و ارتقا.
- فیلتر دسته‌بندی ماژول‌ها (پایه، عملیات، تیم، شبکه‌های اجتماعی، هوش مصنوعی، بازاریابی).
- سوئیچ‌های روشن/خاموش با دیالوگ تایید و هشدار عواقب (همراه با تاکید بر بقای داده‌ها).
- نشانگرهای وضعیت پیش‌نیازها و وابستگی‌ها.
- کارت‌های مانیتورینگ سلامت سرویس‌های خارجی با کلید شبیه‌سازی تست قطع/وصل.
