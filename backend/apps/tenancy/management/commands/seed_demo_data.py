from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.accounts.models import User
from apps.tenancy.models import Business, Store, StoreMembership, Role
from apps.inventory.models import Warehouse, InventoryBalance
from apps.inventory.services import adjust_stock
from apps.catalog.models import Category, Product, ProductVariant
from apps.orders.models import Order, OrderItem, Customer, OrderStatus, PaymentStatus, FulfillmentStatus, OrderChannel
from apps.orders.services import create_order, fulfill_order
from apps.payments.models import PaymentTransaction, PaymentMethod, PaymentVerificationStatus
from apps.payments.services import verify_payment_transaction
from apps.fulfillment.models import Shipment, Carrier, ShipmentStatus
from apps.daily_actions.services import sync_daily_actions_for_store
from apps.suppliers.models import Supplier, PurchaseOrder, PurchaseOrderItem, PurchaseOrderStatus
from apps.returns.models import ReturnRequest, ReturnItem, ReturnStatus, RefundStatus, ReturnReason
from apps.marketing.models import Coupon, DiscountType
from apps.automation.models import AutomationRule, TriggerEvent
from apps.crm.services import recalculate_all_store_customers
from apps.social_inbox.models import ConversationThread, ChatMessage, ThreadChannel, ThreadStatus, SenderType

class Command(BaseCommand):
    help = "Seeds comprehensive realistic demo data for ShopPilot (Persian e-commerce)"

    def handle(self, *args, **options):
        self.stdout.write("Seeding ShopPilot demo data...")

        # 1. Create Demo User
        user, created = User.objects.get_or_create(
            email="demo@shoppilot.io",
            defaults={
                'full_name': "مهندس علیرضا رضایی",
                'phone_number': "09121112233",
                'is_staff': True,
                'is_superuser': True,
            }
        )
        user.set_password("password123")
        user.save()

        # 2. Business & Store
        business, _ = Business.objects.get_or_create(
            name="برند پوشاک و لایف‌استایل لوتوس",
            owner=user
        )

        store, _ = Store.objects.get_or_create(
            business=business,
            name="شعبه مرکزی و فروش آنلاین لوتوس",
            defaults={'currency': Store.Currency.IRT, 'timezone': 'Asia/Tehran'}
        )

        StoreMembership.objects.get_or_create(
            store=store,
            user=user,
            defaults={'role': Role.OWNER, 'is_active': True}
        )

        # 3. Warehouses
        wh_central, _ = Warehouse.objects.get_or_create(
            store=store,
            name="انبار مرکزی تهران",
            defaults={'code': 'WH-TEH-01', 'address': 'تهران، خیابان جمهوری، کوچه لاله، پلاک ۱۲', 'is_default': True}
        )
        wh_west, _ = Warehouse.objects.get_or_create(
            store=store,
            name="انبار غرب (صادقیه)",
            defaults={'code': 'WH-TEH-02', 'address': 'تهران، صادقیه، بلوار کاشانی', 'is_default': False}
        )

        # 4. Categories
        cat_women, _ = Category.objects.get_or_create(store=store, name="مانتو و پیراهن", slug="manto-dress")
        cat_shoes, _ = Category.objects.get_or_create(store=store, name="کیف و کفش", slug="bags-shoes")
        cat_acc, _ = Category.objects.get_or_create(store=store, name="اکسسوری و شال", slug="accessories")

        # 5. Products & Variants
        products_data = [
            {
                'name': "مانتو کتی ژاکارد طرح بهار",
                'category': cat_women,
                'brand': "لوتوس",
                'variants': [
                    {'name': "مشکی / سایز ۱ (۳۶-۳۸)", 'sku': "MANTO-JK-BLK-S1", 'cost': Decimal('320000'), 'retail': Decimal('580000'), 'initial_stock': 25},
                    {'name': "مشکی / سایز ۲ (۴۰-۴۲)", 'sku': "MANTO-JK-BLK-S2", 'cost': Decimal('320000'), 'retail': Decimal('580000'), 'initial_stock': 18},
                    {'name': "کرم / سایز ۱ (۳۶-۳۸)", 'sku': "MANTO-JK-CRM-S1", 'cost': Decimal('320000'), 'retail': Decimal('580000'), 'initial_stock': 3},  # LOW STOCK
                ]
            },
            {
                'name': "شومیز لنین یقه انگلیسی",
                'category': cat_women,
                'brand': "لوتوس",
                'variants': [
                    {'name': "سفید / فری سایز", 'sku': "SHMZ-LN-WHT-FS", 'cost': Decimal('190000'), 'retail': Decimal('390000'), 'initial_stock': 40},
                    {'name': "سبز زیتونی / فری سایز", 'sku': "SHMZ-LN-OLV-FS", 'cost': Decimal('190000'), 'retail': Decimal('390000'), 'initial_stock': 2},  # LOW STOCK
                ]
            },
            {
                'name': "کیف دوشی چرم طبیعی رزا",
                'category': cat_shoes,
                'brand': "دست‌دوز چرمیران",
                'variants': [
                    {'name': "عسلی", 'sku': "BAG-ROSA-HNY", 'cost': Decimal('480000'), 'retail': Decimal('890000'), 'initial_stock': 12},
                    {'name': "قهوه‌ای تیره", 'sku': "BAG-ROSA-BRN", 'cost': Decimal('480000'), 'retail': Decimal('890000'), 'initial_stock': 8},
                ]
            },
            {
                'name': "شال ابریشم توییل والنتینو",
                'category': cat_acc,
                'brand': "ایتالیا دیزاین",
                'variants': [
                    {'name': "طرح مینیمال طوسی", 'sku': "SHAWL-TWL-GRY", 'cost': Decimal('95000'), 'retail': Decimal('220000'), 'initial_stock': 30},
                    {'name': "طرح سنتی سورمه‌ای", 'sku': "SHAWL-TWL-NVY", 'cost': Decimal('95000'), 'retail': Decimal('220000'), 'initial_stock': 22},
                ]
            }
        ]

        created_variants = []
        for p_info in products_data:
            p, _ = Product.objects.get_or_create(
                store=store,
                name=p_info['name'],
                defaults={'category': p_info['category'], 'brand': p_info['brand'], 'status': 'ACTIVE'}
            )
            for v_info in p_info['variants']:
                v, _ = ProductVariant.objects.get_or_create(
                    store=store,
                    sku=v_info['sku'],
                    defaults={
                        'product': p,
                        'name': v_info['name'],
                        'cost_price': v_info['cost'],
                        'retail_price': v_info['retail'],
                    }
                )
                created_variants.append(v)
                adjust_stock(
                    store=store,
                    warehouse=wh_central,
                    variant=v,
                    new_on_hand=v_info['initial_stock'],
                    reason="موجودی اولیه راه‌اندازی سیستم",
                    user=user
                )

        # 6. Sample Realistic Orders
        customers_info = [
            {'name': "سارا محمدی", 'phone': "09123456789", 'city': "تهران", 'address': "سعادت‌آباد، خیابان علامه شمالی، پلاک ۱۸"},
            {'name': "نیلوفر حسینی", 'phone': "09351234567", 'city': "اصفهان", 'address': "چهارباغ عباسی، کوچه فردوسی، مجتمع نگین"},
            {'name': "مریم کاظمی", 'phone': "09139876543", 'city': "شیراز", 'address': "خیابان زرگری، کوچه ۵، پلاک ۲"},
            {'name': "مهسا ابراهیمی", 'phone': "09154443322", 'city': "مشهد", 'address': "بلوار سجاد، خیابان بهار، پلاک ۴۰"},
            {'name': "زهرا شریفی", 'phone': "09176543210", 'city': "تبریز", 'address': "ولیعصر، خیابان تختی، پلاک ۷"},
        ]

        # Order 1: Instagram order, Paid and Fulfilled
        v1 = created_variants[0]
        v2 = created_variants[3]
        order1 = create_order(
            store=store,
            customer_data=customers_info[0],
            items_data=[
                {'variant_id': str(v1.id), 'quantity': 1, 'unit_price': v1.retail_price},
                {'variant_id': str(v2.id), 'quantity': 1, 'unit_price': v2.retail_price},
            ],
            warehouse=wh_central,
            channel=OrderChannel.INSTAGRAM,
            shipping_cost=Decimal('45000'),
            notes="سفارش از دایرکت اینستاگرام پیج اصلی",
            user=user
        )
        pay1 = PaymentTransaction.objects.create(
            store=store,
            order=order1,
            method=PaymentMethod.CARD_TO_CARD,
            amount=order1.grand_total,
            payer_card_mask="6037-****-1234",
            reference_number="REF-987654",
            status=PaymentVerificationStatus.VERIFIED
        )
        verify_payment_transaction(pay1, user)
        fulfill_order(order1, tracking_number="21498021110001234567", user=user)

        # Order 2: Telegram order, Pending card-to-card verification
        v3 = created_variants[5]
        order2 = create_order(
            store=store,
            customer_data=customers_info[1],
            items_data=[
                {'variant_id': str(v3.id), 'quantity': 1, 'unit_price': v3.retail_price},
            ],
            warehouse=wh_central,
            channel=OrderChannel.TELEGRAM,
            shipping_cost=Decimal('50000'),
            notes="فیش واریزی در کانال تلگرام ارسال شده",
            user=user
        )
        PaymentTransaction.objects.create(
            store=store,
            order=order2,
            method=PaymentMethod.CARD_TO_CARD,
            amount=order2.grand_total,
            payer_card_mask="5892-****-8819",
            tracking_code="TRK-654321",
            status=PaymentVerificationStatus.PENDING_VERIFICATION,
            receipt_image_url="https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?w=500"
        )

        # Order 3: Website order, Confirmed but Unfulfilled
        v4 = created_variants[7]
        order3 = create_order(
            store=store,
            customer_data=customers_info[2],
            items_data=[
                {'variant_id': str(v4.id), 'quantity': 2, 'unit_price': v4.retail_price},
            ],
            warehouse=wh_central,
            channel=OrderChannel.WOOCOMMERCE,
            shipping_cost=Decimal('45000'),
            notes="پرداخت آنلاین از طریق درگاه سایت",
            user=user
        )
        pay3 = PaymentTransaction.objects.create(
            store=store,
            order=order3,
            method=PaymentMethod.ONLINE_GATEWAY,
            amount=order3.grand_total,
            reference_number="GW-ZARIN-445522",
            status=PaymentVerificationStatus.VERIFIED
        )
        verify_payment_transaction(pay3, user)

        # 7. Seed Team Members & Invitations
        team_members_data = [
            {'email': 'sara@shoppilot.io', 'full_name': 'سارا محمدی', 'role': Role.SOCIAL_MEDIA_MANAGER, 'phone': '09123334455'},
            {'email': 'navid@shoppilot.io', 'full_name': 'نوید کمالی', 'role': Role.CONTENT_CREATOR, 'phone': '09124445566'},
            {'email': 'maryam@shoppilot.io', 'full_name': 'مریم حسینی', 'role': Role.OPS_MANAGER, 'phone': '09125556677'},
        ]
        created_members = {}
        for tm in team_members_data:
            u, _ = User.objects.get_or_create(
                email=tm['email'],
                defaults={'full_name': tm['full_name'], 'phone_number': tm['phone']}
            )
            u.set_password('password123')
            u.save()
            StoreMembership.objects.get_or_create(
                store=store,
                user=u,
                defaults={'role': tm['role'], 'status': 'ACTIVE', 'is_active': True}
            )
            created_members[tm['email']] = u

        # Pending invitation
        from apps.tenancy.models import TeamInvitation, InvitationStatus
        from datetime import timedelta
        TeamInvitation.objects.get_or_create(
            store=store,
            email='arash@shoppilot.io',
            defaults={
                'role': Role.SUPPORT,
                'inviter': user,
                'token': 'inv_demo_arash_12345',
                'status': InvitationStatus.PENDING,
                'expires_at': timezone.now() + timedelta(days=5)
            }
        )

        # 8. Seed Tasks & Categories
        from apps.tasks.models import TaskCategory, Task, TaskPriority, TaskStatus
        from apps.tasks.services import TaskService

        cat_content, _ = TaskCategory.objects.get_or_create(store=store, name="تولید محتوا و رسانه", defaults={'color': '#8B5CF6', 'icon': 'video'})
        cat_ops, _ = TaskCategory.objects.get_or_create(store=store, name="عملیات و لجستیک", defaults={'color': '#10B981', 'icon': 'package'})
        cat_sales, _ = TaskCategory.objects.get_or_create(store=store, name="فروش و امور مالی", defaults={'color': '#F59E0B', 'icon': 'dollar-sign'})

        now = timezone.now()
        today = now.date()

        # Task 1: Shoot Reels for new manteau
        p1 = Product.objects.filter(store=store).first()
        TaskService.create_task(
            store=store,
            creator=user,
            data={
                'title': 'فیلمبرداری و ادیت ریلز مانتو کتی ژاکارد',
                'description': 'ضبط ۳ سناریوی ترند اینستاگرام با مدل در آتلیه مرکزی، ادیت ریتمیک همراه با کال‌تواکشن خرید از دایرکت.',
                'category': cat_content,
                'priority': TaskPriority.HIGH,
                'status': TaskStatus.IN_PROGRESS,
                'assignee': created_members['navid@shoppilot.io'],
                'reviewer': created_members['sara@shoppilot.io'],
                'start_date': today - timedelta(days=1),
                'due_date': today + timedelta(days=2),
                'estimated_hours': Decimal('4.5'),
                'actual_hours': Decimal('2.0'),
                'requires_verification': True,
                'related_product': p1
            },
            checklist_items=[
                {'title': 'آماده‌سازی مانتو و اتوکشی نمونه عکاسی', 'is_completed': True},
                {'title': 'فیلمبرداری پلان‌های کلوزآپ پارچه ژاکارد', 'is_completed': True},
                {'title': 'تدوین و انتخاب موزیک ترند اینستاگرام', 'is_completed': False},
                {'title': 'طراحی کاور جذاب با تیتر قلاب‌دار', 'is_completed': False},
            ]
        )

        # Task 2: Inventory recount
        TaskService.create_task(
            store=store,
            creator=user,
            data={
                'title': 'شمارش موجودی و بسته‌بندی سفارشات معوق انبار مرکزی',
                'description': 'تطبیق فیزیکی قفسه کفش‌های چرم و آماده‌سازی ۳ مرسوله برای تحویل به پیک تیپاکس.',
                'category': cat_ops,
                'priority': TaskPriority.URGENT,
                'status': TaskStatus.TODO,
                'assignee': created_members['maryam@shoppilot.io'],
                'reviewer': user,
                'start_date': today,
                'due_date': today + timedelta(days=1),
                'estimated_hours': Decimal('3.0'),
                'requires_verification': True
            },
            checklist_items=[
                {'title': 'شمارش فیزیکی کفش چرم عسلی سایز ۳۸', 'is_completed': False},
                {'title': 'چاپ لیبل‌های بارکد پستی سفارشات ۱۰۱ و ۱۰۳', 'is_completed': False},
                {'title': 'تحویل به مامور تیپاکس و دریافت کد پیگیری', 'is_completed': False},
            ]
        )

        # Task 3: Verify bank slips
        TaskService.create_task(
            store=store,
            creator=user,
            data={
                'title': 'تأیید فیش‌های کارت به کارت کانال تلگرام',
                'description': 'بررسی ۵ تراکنش بانکی با پیامک‌های گردش حساب سپه و ثبت تأیید در سامانه.',
                'category': cat_sales,
                'priority': TaskPriority.MEDIUM,
                'status': TaskStatus.COMPLETED,
                'assignee': user,
                'due_date': today - timedelta(days=1),
                'completed_at': now - timedelta(hours=3),
                'completion_evidence': 'تمام فیش‌ها با پیامک بانک مطابقت داده شد.'
            }
        )

        # 9. Seed Social Media Accounts, Campaigns & Content
        from apps.social.models import (
            SocialAccount, SocialPlatform, ConnectionMode,
            SocialCampaign, SocialContent, ContentType, ContentStatus, PublishingMode
        )
        from apps.social.services import SocialService

        acc_ig, _ = SocialAccount.objects.get_or_create(
            store=store,
            platform=SocialPlatform.INSTAGRAM,
            handle='@lotus_boutique_fa',
            defaults={
                'display_name': 'مزون و فروشگاه پوشاک لوتوس',
                'is_connected': True,
                'connection_mode': ConnectionMode.MANUAL_TRACKING,
                'follower_count': 24800,
                'bio': 'طراحی و دوخت خاص بانوان 🌿 | ارسال فوری به سراسر کشور | ثبت سفارش از سایت و دایرکت'
            }
        )

        acc_tg, _ = SocialAccount.objects.get_or_create(
            store=store,
            platform=SocialPlatform.TELEGRAM,
            handle='@lotus_store_official',
            defaults={
                'display_name': 'کانال حراج و اطلاع‌رسانی لوتوس',
                'is_connected': True,
                'connection_mode': ConnectionMode.MANUAL_TRACKING,
                'follower_count': 6400,
                'bio': 'اطلاع‌رسانی تخفیف‌های ویژه و شارژ موجودی انبار'
            }
        )

        camp_autumn, _ = SocialCampaign.objects.get_or_create(
            store=store,
            name='کمپین کالکشن پاییزه ۱۴۰۳',
            defaults={
                'objective': 'SALES',
                'budget': Decimal('40000000'),
                'status': 'ACTIVE',
                'start_date': today - timedelta(days=7),
                'end_date': today + timedelta(days=21),
                'description': 'تمرکز بر مانتوهای کتی و بارانی‌های پاییزی با تخفیف افتتاحیه فصل'
            }
        )

        # Content 1: Published Reel with high engagement
        c_published, _ = SocialContent.objects.get_or_create(
            store=store,
            title='ریلز رونمایی استایل پاییزی با مانتو کتی ژاکارد',
            defaults={
                'account': acc_ig,
                'campaign': camp_autumn,
                'content_type': ContentType.REEL,
                'caption': 'استایلی که این پاییز همه چشم‌ها رو به خودش خیره می‌کنه! ✨ مانتو کتی ژاکارد با بهترین متریال.\nکد محصول: MANTO-JK-01\nبرای سفارش به دایرکت یا لینک بایو سر بزنید.',
                'hashtags': '#مانتو_کتی #استایل_پاییزه #مزون_تهران #پوشاک_زنانه',
                'status': ContentStatus.PUBLISHED,
                'creator': created_members['navid@shoppilot.io'],
                'assignee': created_members['navid@shoppilot.io'],
                'scheduled_at': now - timedelta(days=3),
                'published_at': now - timedelta(days=3),
                'published_url': 'https://instagram.com/p/DB98234Lotus',
                'thumbnail_url': 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=600',
                'related_product': p1
            }
        )

        # Record metrics snapshot for published reel
        SocialService.record_metrics(
            content=c_published,
            metrics_data={
                'reach': 18400,
                'impressions': 24500,
                'likes': 1420,
                'comments': 310,
                'shares': 225,
                'saves': 380,
                'clicks': 490,
                'attributed_orders_count': 18,
                'attributed_revenue': Decimal('54800000')
            }
        )

        # Content 2: Scheduled Story for today evening
        SocialContent.objects.get_or_create(
            store=store,
            title='استوری یادآوری موجودی محدود کرم',
            defaults={
                'account': acc_ig,
                'campaign': camp_autumn,
                'content_type': ContentType.STORY,
                'caption': 'فقط ۳ عدد از مانتو کتی ژاکارد رنگ کرم در انبار باقیمانده! ⏳ باکس سوالات سفارش سریع باز شد.',
                'status': ContentStatus.SCHEDULED,
                'creator': created_members['sara@shoppilot.io'],
                'assignee': created_members['sara@shoppilot.io'],
                'scheduled_at': now + timedelta(hours=4),
                'thumbnail_url': 'https://images.unsplash.com/photo-1539109136881-3be0616acf4b?w=600',
                'publishing_mode': PublishingMode.MANUAL_REMINDER,
                'related_product': p1
            }
        )

        # Content 3: In Review Carousel for weekend
        c_review, _ = SocialContent.objects.get_or_create(
            store=store,
            title='پست اسلایدی نحوه ست کردن کیف چرم دوشی با پالتو',
            defaults={
                'account': acc_ig,
                'campaign': camp_autumn,
                'content_type': ContentType.CAROUSEL,
                'caption': 'ورق بزنید! ۵ ایده جذاب ست کردن کیف چرم عسلی در مهمانی و محل کار 👜 کد تخفیف اختصاصی در اسلاید آخر.',
                'hashtags': '#ست_کیف_کفش #کیف_چرم #استایل_شیک',
                'status': ContentStatus.READY_FOR_REVIEW,
                'creator': created_members['navid@shoppilot.io'],
                'assignee': created_members['sara@shoppilot.io'],
                'scheduled_at': now + timedelta(days=2),
                'thumbnail_url': 'https://images.unsplash.com/photo-1548036328-c9fa89d128fa?w=600',
                'publishing_mode': PublishingMode.MANUAL_REMINDER
            }
        )

        # 10. Suppliers & Purchase Orders
        supp1, _ = Supplier.objects.get_or_create(
            store=store,
            name="تولیدی و بافندگی پارس مد",
            defaults={
                'contact_name': "مهندس اکبری",
                'phone_number': "09121239988",
                'email': "info@parsmod.ir",
                'lead_time_days': 4,
                'payment_terms': 'NET_30'
            }
        )

        supp2, _ = Supplier.objects.get_or_create(
            store=store,
            name="چرم طبیعی تبریز فاخر",
            defaults={
                'contact_name': "حاج رضا تبریزی",
                'phone_number': "09143334455",
                'lead_time_days': 2,
                'payment_terms': 'CASH'
            }
        )

        po1, _ = PurchaseOrder.objects.get_or_create(
            store=store,
            po_number="PO-261012-001",
            defaults={
                'supplier': supp1,
                'warehouse': wh_central,
                'status': PurchaseOrderStatus.APPROVED,
                'total_amount': Decimal('7500000'),
                'expected_delivery_date': (now + timedelta(days=3)).date(),
                'notes': 'تامین مانتو کتی بهاره'
            }
        )
        sample_variant = ProductVariant.objects.filter(store=store).first()
        if sample_variant:
            PurchaseOrderItem.objects.get_or_create(
                purchase_order=po1,
                variant=sample_variant,
                defaults={
                    'quantity_ordered': 25,
                    'quantity_received': 0,
                    'unit_cost': Decimal('300000'),
                    'total_cost': Decimal('7500000')
                }
            )

        # 11. Customer Returns RMA
        first_completed_order = Order.objects.filter(store=store, order_status=OrderStatus.COMPLETED).first()
        if first_completed_order and first_completed_order.items.exists():
            rma1, _ = ReturnRequest.objects.get_or_create(
                store=store,
                rma_number="RMA-261012-101",
                defaults={
                    'order': first_completed_order,
                    'customer': first_completed_order.customer,
                    'status': ReturnStatus.REQUESTED,
                    'refund_status': RefundStatus.PENDING,
                    'refund_amount': Decimal('450000'),
                    'customer_notes': 'سایز برای من مقداری گشاد بود و تمایل به تعویض دارم.'
                }
            )
            first_item = first_completed_order.items.first()
            ReturnItem.objects.get_or_create(
                return_request=rma1,
                order_item=first_item,
                variant=first_item.variant,
                defaults={
                    'quantity': 1,
                    'reason': ReturnReason.SIZE_MISMATCH
                }
            )

        # 12. Marketing Coupons
        Coupon.objects.get_or_create(
            store=store,
            code="LOTUS20",
            defaults={
                'description': 'تخفیف ۲۰ درصدی به مناسبت جشنواره پاییزه',
                'discount_type': DiscountType.PERCENTAGE,
                'discount_value': Decimal('20'),
                'min_order_amount': Decimal('300000'),
                'max_discount_amount': Decimal('150000'),
                'max_uses': 200,
                'uses_count': 14,
                'is_active': True
            }
        )
        Coupon.objects.get_or_create(
            store=store,
            code="WELCOME50K",
            defaults={
                'description': '۵۰ هزار تومان هدیه اولین خرید',
                'discount_type': DiscountType.FIXED_AMOUNT,
                'discount_value': Decimal('50000'),
                'min_order_amount': Decimal('250000'),
                'max_uses': 0,
                'uses_count': 32,
                'is_active': True
            }
        )

        # 13. Automation Rules
        AutomationRule.objects.get_or_create(
            store=store,
            name="ارسال پیامک تایید سفارش و ثبت وظیفه بسته‌بندی",
            defaults={
                'trigger': TriggerEvent.ORDER_PAID,
                'conditions': {},
                'actions': [
                    {'type': 'SEND_SMS', 'template': 'سفارش شما در فروشگاه لوتوس تایید شد.'},
                    {'type': 'CREATE_TASK', 'title': 'آماده‌سازی و بسته‌بندی سفارش پرداختی', 'priority': 'HIGH'}
                ],
                'is_active': True,
                'execution_count': 28
            }
        )

        # 14. CRM RFM Calculation
        recalculate_all_store_customers(store)

        # 15. Unified Social Inbox Threads & Messages
        thread1, _ = ConversationThread.objects.get_or_create(
            store=store,
            contact_handle="@shiva_tehrani",
            defaults={
                'channel': ThreadChannel.INSTAGRAM_DM,
                'contact_name': 'شیوا تهرانی',
                'status': ThreadStatus.OPEN,
                'last_message_preview': 'سلام وقتتون بخیر، مانتو کتی کرم سایز S موجود دارید؟ ارسال به رشت چقدر طول می‌کشه؟'
            }
        )
        ChatMessage.objects.get_or_create(
            thread=thread1,
            text='سلام وقتتون بخیر، مانتو کتی کرم سایز S موجود دارید؟ ارسال به رشت چقدر طول می‌کشه؟',
            defaults={
                'sender_type': SenderType.CUSTOMER
            }
        )

        # 16. Sync Daily Actions
        sync_daily_actions_for_store(store)

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded demo store ID: {store.id}"))
        self.stdout.write(self.style.SUCCESS("Demo credentials: demo@shoppilot.io / password123"))


