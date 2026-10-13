import pytest
from datetime import timedelta
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.tenancy.models import Business, Store, StoreMembership, Role, MembershipStatus
from apps.catalog.models import Product, ProductVariant
from apps.inventory.models import Warehouse
from apps.orders.models import Order, Customer, OrderStatus, PaymentStatus
from apps.audit.models import AuditLog, NotificationPreference
from apps.tasks.models import Task, TaskPriority, TaskStatus
from apps.tasks.serializers import TaskDetailSerializer
from apps.social.models import SocialContent, SocialAccount, SocialPlatform, ContentType, ContentStatus
from apps.social.serializers import SocialContentDetailSerializer
from apps.intelligence.models import CustomerFeedback
from apps.intelligence.serializers import CustomerFeedbackSerializer
from apps.automation.models import AutomationRule, TriggerEvent
from apps.automation.services import execute_actions
from apps.marketing.models import AbandonedCart, AbandonedCartStatus


@pytest.mark.django_db
class TestFieldAndFeaturesRegression:
    @pytest.fixture
    def setup_data(self):
        owner = User.objects.create_user(email="field_owner@test.com", password="pass123", full_name="Field Owner")
        biz = Business.objects.create(name="Field Biz", owner=owner)
        store = Store.objects.create(business=biz, name="Field Store", currency="IRT")
        StoreMembership.objects.create(store=store, user=owner, role=Role.OWNER, status=MembershipStatus.ACTIVE, is_active=True)

        product = Product.objects.create(store=store, name="Sample Leather Wallet")
        variant = ProductVariant.objects.create(
            store=store, product=product, name="Black", sku="WALLET-BLK",
            retail_price=250000, cost_price=120000
        )

        customer = Customer.objects.create(
            store=store, full_name="Reza Mohammadi", phone_number="09129998877"
        )

        warehouse = Warehouse.objects.create(store=store, name="Default WH", is_default=True)
        order = Order.objects.create(
            store=store, customer=customer, warehouse=warehouse, order_number="ORD-FIELD-01",
            total_items_price=250000, grand_total=250000
        )

        return {
            'owner': owner,
            'store': store,
            'product': product,
            'variant': variant,
            'customer': customer,
            'order': order
        }

    def test_team_activity_summary_and_audit_export(self, setup_data):
        store = setup_data['store']
        owner = setup_data['owner']

        # Create audit log events with the custom User model
        AuditLog.objects.create(
            store=store,
            user=owner,
            action="PRODUCT_CREATED",
            target_type="Product",
            target_id="p-1",
            ip_address="192.168.1.1"
        )

        client = APIClient()
        client.force_authenticate(user=owner)

        # 1. TeamActivitySummaryView must execute without FieldError
        res_summary = client.get('/api/v1/audit/team-activity/?days=30', HTTP_X_STORE_ID=str(store.id))
        assert res_summary.status_code == status.HTTP_200_OK
        assert 'team_activities' in res_summary.data
        acts = res_summary.data['team_activities']
        assert len(acts) > 0
        assert acts[0]['user_name'] == "Field Owner"

        # 2. AuditExportCSVView must export CSV without AttributeError and formula-sanitize
        res_csv = client.get('/api/v1/audit/export-csv/', HTTP_X_STORE_ID=str(store.id))
        assert res_csv.status_code == status.HTTP_200_OK
        csv_content = res_csv.content.decode('utf-8-sig')
        assert 'شناسه' in csv_content
        assert 'Field Owner' in csv_content

        # 3. NotificationPreference string representation
        pref, _ = NotificationPreference.objects.get_or_create(store=store, user=owner)
        assert "Field Owner" in str(pref) or "field_owner@test.com" in str(pref)

    def test_task_and_social_related_product_serialization(self, setup_data):
        store = setup_data['store']
        owner = setup_data['owner']
        product = setup_data['product']

        # Create Task linked to Product
        task = Task.objects.create(
            store=store,
            title="Inspect wallet packaging",
            creator=owner,
            related_product=product,
            priority=TaskPriority.HIGH
        )
        task_data = TaskDetailSerializer(task).data
        assert task_data['related_product_title'] == "Sample Leather Wallet"

        # Create SocialContent linked to Product
        account = SocialAccount.objects.create(
            store=store, platform=SocialPlatform.INSTAGRAM, handle="test_wallet"
        )
        content = SocialContent.objects.create(
            store=store,
            account=account,
            creator=owner,
            content_type=ContentType.REEL,
            title="Wallet Unboxing",
            caption="High quality leather",
            related_product=product
        )
        content_data = SocialContentDetailSerializer(content).data
        assert content_data['related_product_title'] == "Sample Leather Wallet"

    def test_customer_feedback_phone_serialization(self, setup_data):
        store = setup_data['store']
        customer = setup_data['customer']
        order = setup_data['order']

        feedback = CustomerFeedback.objects.create(
            store=store,
            customer=customer,
            order=order,
            rating=5,
            comment="Great product quality!"
        )
        fb_data = CustomerFeedbackSerializer(feedback).data
        assert fb_data['customer_phone'] == "09129998877"
        assert fb_data['customer_name'] == "Reza Mohammadi"

    def test_automation_execute_actions_valid_creator(self, setup_data):
        store = setup_data['store']
        rule = AutomationRule.objects.create(
            store=store,
            name="Notify on low stock",
            trigger=TriggerEvent.STOCK_LOW,
            actions=[{'type': 'CREATE_TASK', 'title': 'Restock Wallet'}]
        )

        # 1. Real execution creates Task with valid creator
        output = execute_actions(rule=rule, actions=rule.actions, payload={}, dry_run=False)
        assert "با موفقیت" in output

        task = Task.objects.filter(store=store, title="Restock Wallet").first()
        assert task is not None
        assert task.creator == store.business.owner

        # 2. Dry run simulation does not create tasks
        initial_count = Task.objects.filter(store=store).count()
        sim_output = execute_actions(rule=rule, actions=rule.actions, payload={}, dry_run=True)
        assert "[شبیه‌سازی]" in sim_output
        assert Task.objects.filter(store=store).count() == initial_count

    def test_abandoned_cart_trigger_recovery(self, setup_data):
        store = setup_data['store']
        owner = setup_data['owner']
        customer = setup_data['customer']

        cart = AbandonedCart.objects.create(
            store=store,
            customer=customer,
            phone_or_email="09129998877",
            total_amount=250000,
            status=AbandonedCartStatus.PENDING
        )

        client = APIClient()
        client.force_authenticate(user=owner)

        from unittest import mock

        # 1. Trigger recovery succeeds with accepted gateway response
        with mock.patch('apps.features.adapters.SMSGateway.send_sms', return_value={'status': 'ACCEPTED', 'message_id': 'ack_123'}):
            res1 = client.post(
                f'/api/v1/marketing/abandoned-carts/{cart.id}/trigger-recovery/',
                HTTP_X_STORE_ID=str(store.id)
            )
            assert res1.status_code == status.HTTP_200_OK
            cart.refresh_from_db()
            assert cart.recovery_sms_sent_at is not None

        # 2. Triggering recovery again within 2 hours is rejected by anti-spam cooldown
        res_cooldown = client.post(
            f'/api/v1/marketing/abandoned-carts/{cart.id}/trigger-recovery/',
            HTTP_X_STORE_ID=str(store.id)
        )
        assert res_cooldown.status_code == status.HTTP_429_TOO_MANY_REQUESTS

        # 3. Already recovered cart cannot be triggered
        cart.status = AbandonedCartStatus.RECOVERED
        cart.recovery_sms_sent_at = timezone.now() - timedelta(hours=3)
        cart.save()

        res_recovered = client.post(
            f'/api/v1/marketing/abandoned-carts/{cart.id}/trigger-recovery/',
            HTTP_X_STORE_ID=str(store.id)
        )
        assert res_recovered.status_code == status.HTTP_400_BAD_REQUEST
