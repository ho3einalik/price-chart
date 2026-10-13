import pytest
from decimal import Decimal
from rest_framework import status
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.tenancy.models import Business, Store, StoreMembership, Role, MembershipStatus
from apps.catalog.models import Product, ProductVariant
from apps.inventory.models import Warehouse, InventoryBalance, InventoryMovement
from apps.inventory.services import commit_stock_sale, InsufficientStockError, transfer_stock
from apps.orders.models import Order, OrderItem, Customer, OrderStatus, PaymentStatus
from apps.orders.services import create_order, fulfill_order, cancel_order
from apps.returns.models import ReturnRequest, ReturnItem, ReturnStatus, ReturnAction, ItemCondition
from apps.returns.services import create_return_request
from apps.suppliers.models import Supplier, PurchaseOrder, PurchaseOrderItem, PurchaseOrderStatus
from apps.suppliers.services import receive_po_goods
from apps.finance.models import AccountsPayableReceivable, DebtEntityType, DebtStatus
from apps.wholesale_pos.models import POSTerminal, POSRegisterSession, POSSessionStatus
from apps.wholesale_pos.services import pos_quick_checkout


@pytest.mark.django_db
class TestCommerceIntegrityRegression:
    @pytest.fixture
    def setup_commerce(self):
        owner = User.objects.create_user(email="comm_owner@test.com", password="pass123", full_name="Commerce Owner")
        biz = Business.objects.create(name="Comm Biz", owner=owner)
        store = Store.objects.create(business=biz, name="Comm Store", currency="IRT")
        StoreMembership.objects.create(store=store, user=owner, role=Role.OWNER, status=MembershipStatus.ACTIVE, is_active=True)

        warehouse1 = Warehouse.objects.create(store=store, name="Main Warehouse", is_default=True)
        warehouse2 = Warehouse.objects.create(store=store, name="Secondary Warehouse")

        product = Product.objects.create(store=store, name="T-Shirt")
        variant = ProductVariant.objects.create(
            store=store, product=product, name="Blue / L", sku="TSHIRT-BLU-L",
            retail_price=Decimal('150000'), cost_price=Decimal('80000')
        )

        balance1 = InventoryBalance.objects.create(
            store=store, warehouse=warehouse1, variant=variant, on_hand_quantity=5, reserved_quantity=0
        )

        customer = Customer.objects.create(
            store=store, full_name="Customer Ali", phone_number="09123334455"
        )

        return {
            'owner': owner,
            'store': store,
            'wh1': warehouse1,
            'wh2': warehouse2,
            'variant': variant,
            'customer': customer,
            'balance1': balance1
        }

    def test_overselling_rejected_on_stock_sale(self, setup_commerce):
        store = setup_commerce['store']
        wh1 = setup_commerce['wh1']
        variant = setup_commerce['variant']
        balance1 = setup_commerce['balance1']

        # Available on hand is 5. Attempting to sell 10 must raise InsufficientStockError
        with pytest.raises(InsufficientStockError) as exc_info:
            commit_stock_sale(store=store, warehouse=wh1, variant=variant, quantity=10, reference="TEST-OVERSELL")

        assert "کافی نیست" in str(exc_info.value)

        # Balance must remain unchanged (not clamped to 0)
        balance1.refresh_from_db()
        assert balance1.on_hand_quantity == 5

    def test_wholesale_pos_oversell_rejected(self, setup_commerce):
        store = setup_commerce['store']
        variant = setup_commerce['variant']
        wh1 = setup_commerce['wh1']
        owner = setup_commerce['owner']

        terminal = POSTerminal.objects.create(store=store, name="Terminal 1", warehouse=wh1)
        session = POSRegisterSession.objects.create(store=store, terminal=terminal, opened_by=owner, status=POSSessionStatus.OPEN)

        # Attempt to checkout 10 units when only 5 exist
        items = [{'variant_id': str(variant.id), 'quantity': 10, 'unit_price': 150000}]

        with pytest.raises(DjangoValidationError) as exc_info:
            pos_quick_checkout(
                store=store,
                session_id=str(session.id),
                items_data=items,
                user=owner
            )

        assert "موجودی کافی" in str(exc_info.value)

    def test_duplicate_order_fulfillment_idempotent(self, setup_commerce):
        store = setup_commerce['store']
        variant = setup_commerce['variant']
        wh1 = setup_commerce['wh1']
        owner = setup_commerce['owner']

        customer_data = {'full_name': 'Customer Ali', 'phone_number': '09123334455'}
        items_data = [{'variant_id': str(variant.id), 'quantity': 2, 'unit_price': 150000}]
        order = create_order(store=store, customer_data=customer_data, items_data=items_data, warehouse=wh1, user=owner)

        # First fulfillment
        order, shipment1 = fulfill_order(order=order, user=owner, tracking_number="TRACK-111")
        assert order.order_status == OrderStatus.FULFILLED

        balance = InventoryBalance.objects.get(store=store, variant=variant, warehouse=wh1)
        assert balance.on_hand_quantity == 3  # 5 - 2 = 3

        # Second fulfillment call must be idempotent and not deduct stock again
        order, shipment2 = fulfill_order(order=order, user=owner, tracking_number="TRACK-222")
        assert shipment2.id == shipment1.id

        balance.refresh_from_db()
        assert balance.on_hand_quantity == 3  # Still 3!

    def test_cancellation_of_fulfilled_order_rejected(self, setup_commerce):
        store = setup_commerce['store']
        variant = setup_commerce['variant']
        wh1 = setup_commerce['wh1']
        owner = setup_commerce['owner']

        customer_data = {'full_name': 'Customer Ali', 'phone_number': '09123334455'}
        items_data = [{'variant_id': str(variant.id), 'quantity': 1, 'unit_price': 150000}]
        order = create_order(store=store, customer_data=customer_data, items_data=items_data, warehouse=wh1, user=owner)
        order, _ = fulfill_order(order=order, user=owner)

        # Cancelling an already fulfilled order must be rejected (forces RMA return workflow)
        with pytest.raises(ValueError) as exc:
            cancel_order(order=order, reason="Customer changed mind")

        assert "قابل لغو مستقیم نیست" in str(exc.value)

    def test_cumulative_return_quantity_validation(self, setup_commerce):
        store = setup_commerce['store']
        variant = setup_commerce['variant']
        wh1 = setup_commerce['wh1']
        owner = setup_commerce['owner']

        customer_data = {'full_name': 'Customer Ali', 'phone_number': '09123334455'}
        items_data = [{'variant_id': str(variant.id), 'quantity': 2, 'unit_price': 150000}]
        order = create_order(store=store, customer_data=customer_data, items_data=items_data, warehouse=wh1, user=owner)
        order, _ = fulfill_order(order=order, user=owner)

        order_item = order.items.first()

        # First return for 1 unit succeeds
        ret1 = create_return_request(
            order=order,
            items_data=[{'order_item': order_item, 'quantity': 1, 'reason': 'DEFECTIVE'}],
            user=owner
        )
        assert ret1.status == ReturnStatus.REQUESTED

        # Second return requesting 2 units exceeds remaining returnable quantity (2 - 1 = 1 returnable)
        with pytest.raises(DjangoValidationError) as exc:
            create_return_request(
                order=order,
                items_data=[{'order_item': order_item, 'quantity': 2, 'reason': 'SIZE_MISMATCH'}],
                user=owner
            )

        assert "مانده قابل مرجوعی" in str(exc.value)

    def test_supplier_po_receipt_creates_accounts_payable(self, setup_commerce):
        store = setup_commerce['store']
        variant = setup_commerce['variant']
        wh1 = setup_commerce['wh1']
        owner = setup_commerce['owner']

        supplier = Supplier.objects.create(store=store, name="Major Garments Co", contact_name="Mr. Karimi")
        po = PurchaseOrder.objects.create(
            store=store, supplier=supplier, warehouse=wh1, po_number="PO-TEST-99", status=PurchaseOrderStatus.APPROVED
        )
        po_item = PurchaseOrderItem.objects.create(
            purchase_order=po, variant=variant, quantity_ordered=10, unit_cost=80000, total_cost=800000
        )

        receive_po_goods(
            po=po,
            receipts_data=[{'item_id': str(po_item.id), 'quantity_received': 10}],
            user=owner
        )

        # Verifies stock was received
        balance = InventoryBalance.objects.get(store=store, variant=variant, warehouse=wh1)
        assert balance.on_hand_quantity == 15  # 5 + 10 = 15

        # Verifies Accounts Payable debt record was generated
        ap_record = AccountsPayableReceivable.objects.filter(
            store=store,
            entity_type=DebtEntityType.SUPPLIER_DEBT,
            supplier=supplier
        ).first()

        assert ap_record is not None
        assert ap_record.total_amount == Decimal('800000')
        assert ap_record.remaining_balance == Decimal('800000')

    def test_accounts_payable_receivable_payment_validation(self, setup_commerce):
        store = setup_commerce['store']
        owner = setup_commerce['owner']
        customer = setup_commerce['customer']

        record = AccountsPayableReceivable.objects.create(
            store=store,
            entity_type=DebtEntityType.CUSTOMER_CREDIT,
            customer=customer,
            title="B2B Shop A",
            total_amount=Decimal('500000'),
            paid_amount=Decimal('0')
        )

        client = APIClient()
        client.force_authenticate(user=owner)

        # 1. Zero or negative amount rejected
        res_zero = client.post(
            f'/api/v1/finance/debts/{record.id}/pay/',
            {'amount': 0},
            HTTP_X_STORE_ID=str(store.id)
        )
        assert res_zero.status_code == status.HTTP_400_BAD_REQUEST

        # 2. Overpayment rejected
        res_over = client.post(
            f'/api/v1/finance/debts/{record.id}/pay/',
            {'amount': 600000},
            HTTP_X_STORE_ID=str(store.id)
        )
        assert res_over.status_code == status.HTTP_400_BAD_REQUEST

        # 3. Valid payment accepted and decrements balance
        res_ok = client.post(
            f'/api/v1/finance/debts/{record.id}/pay/',
            {'amount': 200000},
            HTTP_X_STORE_ID=str(store.id)
        )
        assert res_ok.status_code == status.HTTP_200_OK
        record.refresh_from_db()
        assert record.remaining_balance == Decimal('300000')

    def test_financial_export_csv_and_statement(self, setup_commerce):
        store = setup_commerce['store']
        owner = setup_commerce['owner']

        client = APIClient()
        client.force_authenticate(user=owner)

        # Financial statement
        res_stmt = client.get('/api/v1/finance/statement/?days=30', HTTP_X_STORE_ID=str(store.id))
        assert res_stmt.status_code == status.HTTP_200_OK
        assert 'gross_sales' in res_stmt.data
        assert 'net_operating_profit' in res_stmt.data

        # Financial CSV Export (escapes formulas and uses UTF-8 BOM)
        res_csv = client.get('/api/v1/finance/export-csv/', HTTP_X_STORE_ID=str(store.id))
        assert res_csv.status_code == status.HTTP_200_OK
        assert res_csv['Content-Type'].startswith('text/csv')
        csv_text = res_csv.content.decode('utf-8-sig')
        assert 'فروش ناخالص (Gross Sales)' in csv_text
