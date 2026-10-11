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

        # 7. Sync Daily Actions
        sync_daily_actions_for_store(store)

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded demo store ID: {store.id}"))
        self.stdout.write(self.style.SUCCESS("Demo credentials: demo@shoppilot.io / password123"))

