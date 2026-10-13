import pytest
import io
import csv
from decimal import Decimal
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from apps.tenancy.models import Store, Business, StoreMembership, Role
from apps.accounts.models import User
from apps.features.models import SubscriptionTier, StoreFeatureSetting
from apps.features.services import FeatureService
from apps.catalog.models import Category, Product, ProductVariant, ProductPriceHistory
from apps.inventory.models import Warehouse, InventoryBalance, InventoryMovement, MovementType, StockCycleCount, StockCycleCountItem, CycleCountStatus
from apps.inventory.services import (
    get_or_create_balance, adjust_stock,
    start_cycle_count, record_cycle_count_items, reconcile_cycle_count
)
from apps.orders.models import Customer, Order, OrderItem, OrderStatus, PaymentStatus, FulfillmentStatus, OrderChannel
from apps.orders.services import create_order
from apps.returns.models import ReturnRequest, ReturnItem, ReturnStatus, RefundStatus, ReturnAction, ItemCondition
from apps.returns.services import create_return_request, approve_return_request, inspect_and_process_return
from apps.wholesale_pos.models import B2BClientProfile, VolumeTierDiscount, POSTerminal, POSRegisterSession, ProformaInvoice, ProformaStatus
from apps.wholesale_pos.services import pos_quick_checkout, create_quick_sku_order, generate_pos_receipt


@pytest.fixture
def env(db):
    user = User.objects.create_user(
        email='saas_owner@shoppilot.ir',
        phone_number='09121000001',
        password='Password123!',
        full_name='Owner SaaS'
    )
    biz = Business.objects.create(name='SaaS Test Biz', owner=user)
    store = Store.objects.create(
        business=biz,
        name='SaaS Store 1'
    )
    StoreFeatureSetting.objects.create(store=store, tier=SubscriptionTier.FREE)
    StoreMembership.objects.create(store=store, user=user, role=Role.OWNER, is_active=True)

    warehouse = Warehouse.objects.create(
        store=store,
        name='انبار مرکزی',
        is_default=True,
        is_active=True
    )

    client = APIClient()
    client.force_authenticate(user=user)
    client.defaults['HTTP_X_STORE_ID'] = str(store.id)

    return {
        'user': user,
        'store': store,
        'warehouse': warehouse,
        'client': client
    }


@pytest.mark.django_db
class TestPlanQuotaEnforcement:
    def test_quota_checking_and_denial(self, env):
        store = env['store']
        # On FREE plan: max_products is 50, max_members is 2, max_stores is 1
        allowed, current, limit, msg = FeatureService.check_plan_quota(store, 'products')
        assert allowed is True
        assert limit == 50

        # Simulate reaching limit
        allowed, current, limit, msg = FeatureService.check_plan_quota(store, 'products', increment=51)
        assert allowed is False

        # enforce_plan_quota raises PermissionDenied
        with pytest.raises(PermissionDenied) as excinfo:
            FeatureService.enforce_plan_quota(store, 'products', increment=51)
        assert 'پلن اشتراک' in str(excinfo.value) or 'سقف مجاز' in str(excinfo.value)


@pytest.mark.django_db
class TestCatalogBulkUpdateAndPriceHistory:
    def test_bulk_update_and_price_history_logging(self, env):
        store = env['store']
        client = env['client']
        wh = env['warehouse']

        # Create product & variant
        prod = Product.objects.create(store=store, name='کفش ورزشی', status='ACTIVE')
        var = ProductVariant.objects.create(
            store=store,
            product=prod,
            name='سایز ۴۲',
            sku='SHOE-42',
            retail_price=Decimal('500000'),
            cost_price=Decimal('300000'),
            is_active=True
        )

        # Call bulk update endpoint
        payload = {
            'items': [
                {
                    'variant_id': str(var.id),
                    'retail_price': 650000,
                    'cost_price': 350000,
                    'stock_quantity': 25,
                    'warehouse_id': str(wh.id),
                    'reason': 'تغییر نرخ ارز و تعدیل موجودی'
                }
            ]
        }
        res = client.post('/api/v1/catalog/products/bulk-update/', payload, format='json')
        assert res.status_code == 200
        assert res.data['updated_variants'] == 1

        var.refresh_from_db()
        assert var.retail_price == Decimal('650000')
        assert var.cost_price == Decimal('350000')

        # Check price history recorded
        history = ProductPriceHistory.objects.filter(variant=var).first()
        assert history is not None
        assert history.old_retail_price == Decimal('500000')
        assert history.new_retail_price == Decimal('650000')
        assert history.changed_by == env['user']

        # Check inventory adjusted
        bal = InventoryBalance.objects.get(warehouse=wh, variant=var)
        assert bal.on_hand_quantity == 25


@pytest.mark.django_db
class TestCatalogCSVOperations:
    def test_export_and_import_csv(self, env):
        store = env['store']
        client = env['client']

        prod = Product.objects.create(store=store, name='تی‌شرت نخی', status='ACTIVE')
        var = ProductVariant.objects.create(
            store=store,
            product=prod,
            name='سرمه‌ای',
            sku='TSHIRT-NAVY',
            barcode='1234567890123',
            retail_price=Decimal('250000'),
            cost_price=Decimal('120000')
        )

        # Export CSV
        res = client.get('/api/v1/catalog/products/export-csv/')
        assert res.status_code == 200
        assert 'text/csv' in res['Content-Type']
        content = res.content.decode('utf-8-sig')
        assert 'TSHIRT-NAVY' in content
        assert 'تی‌شرت نخی' in content

        # Import CSV with new product
        csv_data = (
            "نام محصول,کد تنوع (SKU),قیمت فروش (تومان),قیمت خرید (تومان),بارکد,موجودی فیزیکی کل\n"
            "شلوار جین,JEAN-SLIM,450000,200000,9876543210123,15\n"
        )
        import_res = client.post(
            '/api/v1/catalog/products/import-csv/',
            {'csv_content': csv_data},
            format='json'
        )
        assert import_res.status_code == 200
        assert import_res.data['created_products'] == 1

        new_var = ProductVariant.objects.get(store=store, sku='JEAN-SLIM')
        assert new_var.retail_price == Decimal('450000')
        assert new_var.product.name == 'شلوار جین'


@pytest.mark.django_db
class TestCatalogBarcodeLookup:
    def test_barcode_lookup_endpoint(self, env):
        store = env['store']
        client = env['client']

        prod = Product.objects.create(store=store, name='هدفون بلوتوث')
        var = ProductVariant.objects.create(
            store=store,
            product=prod,
            name='مشکی',
            sku='HEADPHONE-BLK',
            barcode='777888999',
            retail_price=Decimal('1200000')
        )

        # Lookup by barcode
        res = client.get(f'/api/v1/catalog/products/barcode/777888999/')
        assert res.status_code == 200
        assert res.data['sku'] == 'HEADPHONE-BLK'

        # Lookup by SKU
        res2 = client.get('/api/v1/catalog/products/barcode/?code=HEADPHONE-BLK')
        assert res2.status_code == 200
        assert res2.data['barcode'] == '777888999'

        # Lookup nonexistent
        res3 = client.get('/api/v1/catalog/products/barcode/?code=NONEXISTENT')
        assert res3.status_code == 404


@pytest.mark.django_db
class TestStockCycleCountWorkflow:
    def test_full_cycle_count_and_reconciliation(self, env):
        store = env['store']
        wh = env['warehouse']
        user = env['user']

        prod = Product.objects.create(store=store, name='کتاب رمان')
        var = ProductVariant.objects.create(store=store, product=prod, name='جلد شومیز', sku='BOOK-01')

        # Set initial stock to 10
        adjust_stock(store=store, warehouse=wh, variant=var, new_on_hand=10, reason='موجودی اولیه')

        # 1. Start Cycle Count
        cc = start_cycle_count(store=store, warehouse=wh, notes='انبارگردانی فصلی', user=user)
        assert cc.status == CycleCountStatus.IN_PROGRESS
        item = cc.items.get(variant=var)
        assert item.system_quantity == 10
        assert item.counted_quantity is None

        # 2. Record Physical Counts (counted 8 -> variance of -2)
        record_cycle_count_items(
            cycle_count=cc,
            items_data=[{'variant_id': str(var.id), 'counted_quantity': 8, 'notes': 'کسری ۲ جلد'}],
            user=user
        )
        item.refresh_from_db()
        assert item.counted_quantity == 8
        assert item.variance == -2

        # 3. Reconcile Cycle Count
        reconcile_cycle_count(cycle_count=cc, user=user)
        cc.refresh_from_db()
        assert cc.status == CycleCountStatus.COMPLETED

        # Verify physical stock adjusted to 8 in warehouse
        bal = InventoryBalance.objects.get(warehouse=wh, variant=var)
        assert bal.on_hand_quantity == 8

        # Verify ledger movement recorded
        mv = InventoryMovement.objects.filter(warehouse=wh, variant=var).order_by('-created_at').first()
        assert mv.movement_type == MovementType.ADJUSTMENT
        assert mv.quantity == -2


@pytest.mark.django_db
class TestReturnItemExchange:
    def test_return_exchange_workflow(self, env):
        store = env['store']
        wh = env['warehouse']
        user = env['user']

        prod = Product.objects.create(store=store, name='پیراهن مردانه')
        var_a = ProductVariant.objects.create(store=store, product=prod, name='سایز L', sku='SHIRT-L', retail_price=Decimal('300000'))
        var_b = ProductVariant.objects.create(store=store, product=prod, name='سایز XL', sku='SHIRT-XL', retail_price=Decimal('300000'))

        # Prepare stock: 5 of L and 5 of XL
        adjust_stock(store=store, warehouse=wh, variant=var_a, new_on_hand=5)
        adjust_stock(store=store, warehouse=wh, variant=var_b, new_on_hand=5)

        # Create and fulfill order with var_a
        order = create_order(
            store=store,
            customer_data={'full_name': 'رضا علوی', 'phone_number': '09129998877'},
            items_data=[{'variant_id': str(var_a.id), 'quantity': 1, 'unit_price': 300000}],
            warehouse=wh,
            user=user
        )
        order.order_status = OrderStatus.FULFILLED
        order.fulfillment_status = FulfillmentStatus.FULFILLED
        order.save()

        order_item = order.items.first()

        # Create Return with Exchange for var_b
        rma = create_return_request(
            order=order,
            items_data=[{'order_item': order_item, 'quantity': 1, 'reason': 'SIZE_MISMATCH'}],
            user=user,
            is_exchange=True,
            exchange_variant=var_b,
            exchange_quantity=1
        )
        assert rma.is_exchange is True
        assert rma.exchange_variant == var_b

        # Approve and inspect return
        approve_return_request(rma=rma, user=user)
        inspect_and_process_return(
            rma=rma,
            inspection_items_data=[{'item_id': str(rma.items.first().id), 'action': ReturnAction.RESTOCK, 'condition': ItemCondition.NEW_UNOPENED}],
            warehouse=wh,
            user=user
        )

        rma.refresh_from_db()
        assert rma.status == ReturnStatus.COMPLETED

        # var_b stock should be reduced by 1 (5 -> 4) for the exchange dispatch
        bal_b = InventoryBalance.objects.get(warehouse=wh, variant=var_b)
        assert bal_b.on_hand_quantity == 4


@pytest.mark.django_db
class TestWholesaleQuickSKUAndPOSReceipt:
    def test_quick_sku_order_and_pos_receipt(self, env):
        store = env['store']
        client_api = env['client']
        wh = env['warehouse']
        user = env['user']

        prod = Product.objects.create(store=store, name='کابل شارژ Type-C')
        var = ProductVariant.objects.create(
            store=store,
            product=prod,
            name='طول ۱ متر',
            sku='CABLE-TYPEC',
            retail_price=Decimal('100000'),
            wholesale_price=Decimal('70000')
        )
        adjust_stock(store=store, warehouse=wh, variant=var, new_on_hand=100)

        # Volume tier discount: >= 20 units -> 60,000 تومان
        VolumeTierDiscount.objects.create(
            store=store,
            variant=var,
            min_quantity=20,
            unit_price=Decimal('60000'),
            tier_label='خرید عمده کارتنی'
        )

        customer = Customer.objects.create(store=store, full_name='شرکت پارس الکترونیک', phone_number='09125554433')
        b2b_profile = B2BClientProfile.objects.create(
            store=store,
            customer=customer,
            company_name='شرکت پارس الکترونیک',
            credit_limit=Decimal('10000000'),
            payment_terms_days=30
        )

        # Quick SKU Order API
        res = client_api.post(
            '/api/v1/wholesale/quick-sku-order/',
            {
                'client_id': str(b2b_profile.id),
                'sku_items': [{'sku': 'CABLE-TYPEC', 'quantity': 25}]
            },
            format='json'
        )
        assert res.status_code == 201
        proforma_id = res.data['proforma_id']
        proforma = ProformaInvoice.objects.get(id=proforma_id)
        # 25 * 60,000 = 1,500,000
        assert proforma.grand_total == Decimal('1500000')

        # Test POS quick sale and receipt generation
        term = POSTerminal.objects.create(store=store, name='صندوق ۱', terminal_code='TERM-01', warehouse=wh)
        session = POSRegisterSession.objects.create(store=store, terminal=term, opened_by=user, opening_cash=Decimal('500000'))

        pos_order = pos_quick_checkout(
            store=store,
            session_id=str(session.id),
            items_data=[{'variant_id': str(var.id), 'quantity': 2, 'unit_price': 100000}],
            customer_phone='09121112233',
            customer_name='علی کریمی',
            user=user
        )

        # Retrieve POS receipt
        receipt_res = client_api.get(f'/api/v1/wholesale/pos/receipt/{pos_order.id}/')
        assert receipt_res.status_code == 200
        receipt = receipt_res.data
        assert receipt['order']['order_number'] == pos_order.order_number
        assert 'thermal_receipt_text' in receipt
        assert 'فاکتور فروش صندوق حضوری' in receipt['thermal_receipt_text']
        assert receipt['financials']['grand_total'] == 200000
