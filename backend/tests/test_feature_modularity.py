import pytest
from decimal import Decimal
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User
from apps.tenancy.models import Business, Store, StoreMembership, Role, MembershipStatus
from apps.features.models import StoreFeatureSetting, SubscriptionTier, IntegrationState
from apps.features.registry import (
    FEATURE_CATALOG,
    FeatureDefinition,
    validate_dependency_graph,
    CircularDependencyError,
    get_feature
)
from apps.features.services import FeatureService
from apps.features.adapters import (
    IntegrationRegistry,
    InstagramIntegrationAdapter,
    AIProviderIntegrationAdapter,
    SMSGatewayIntegrationAdapter
)
from apps.tasks.models import Task, TaskCategory, TaskStatus
from apps.social.models import SocialContent, SocialAccount, SocialPlatform, ContentType, ContentStatus
from apps.orders.models import Order, OrderStatus
from apps.catalog.models import Product


@pytest.mark.django_db
class TestFeatureModularityAndIsolation:
    @pytest.fixture
    def setup_store(self):
        owner = User.objects.create_user(email="mod_owner@test.com", password="password123", full_name="Module Owner")
        staff = User.objects.create_user(email="mod_staff@test.com", password="password123", full_name="Module Staff")

        biz = Business.objects.create(name="Modularity Biz", owner=owner)
        store = Store.objects.create(business=biz, name="Modularity Store")

        StoreMembership.objects.create(store=store, user=owner, role=Role.OWNER, status=MembershipStatus.ACTIVE)
        StoreMembership.objects.create(store=store, user=staff, role=Role.FULFILLMENT_STAFF, status=MembershipStatus.ACTIVE)

        # Default PRO settings
        settings = StoreFeatureSetting.objects.create(
            store=store,
            tier=SubscriptionTier.PRO,
            enabled_features=['tasks.planner', 'social.content_calendar', 'social.analytics'],
            disabled_features=[]
        )

        owner_client = APIClient()
        owner_client.force_authenticate(user=owner)
        owner_client.defaults['HTTP_X_STORE_ID'] = str(store.id)

        staff_client = APIClient()
        staff_client.force_authenticate(user=staff)
        staff_client.defaults['HTTP_X_STORE_ID'] = str(store.id)

        return {
            'owner': owner,
            'staff': staff,
            'store': store,
            'settings': settings,
            'owner_client': owner_client,
            'staff_client': staff_client,
        }

    def test_feature_catalog_and_dag_validation(self):
        """Validates that the production feature registry has no circular dependencies"""
        # Should not raise CircularDependencyError
        validate_dependency_graph(FEATURE_CATALOG)

        # Intentionally craft a circular dependency graph
        cycle_catalog = {
            'feat.a': FeatureDefinition(
                key='feat.a', name_fa='ویژگی الف', description_fa='', category='CORE',
                depends_on=['feat.b']
            ),
            'feat.b': FeatureDefinition(
                key='feat.b', name_fa='ویژگی ب', description_fa='', category='CORE',
                depends_on=['feat.c']
            ),
            'feat.c': FeatureDefinition(
                key='feat.c', name_fa='ویژگی ج', description_fa='', category='CORE',
                depends_on=['feat.a']
            )
        }
        with pytest.raises(CircularDependencyError):
            validate_dependency_graph(cycle_catalog)

    def test_tier_entitlement_restrictions(self, setup_store):
        """Verifies that plan tiers restrict higher-tier features"""
        store = setup_store['store']
        settings = setup_store['settings']

        # Downgrade to FREE plan
        settings.tier = SubscriptionTier.FREE
        settings.save()

        # Core features are allowed on FREE
        allowed, code, _ = FeatureService.check_feature_access(store, 'core.catalog')
        assert allowed is True
        assert code == "ACCESS_GRANTED"

        # PRO features are restricted on FREE
        allowed, code, msg = FeatureService.check_feature_access(store, 'social.auto_publish')
        assert allowed is False
        assert code == "PLAN_RESTRICTED"
        assert "نیازمند اشتراک" in msg

        # Upgrade to PRO
        settings.tier = SubscriptionTier.PRO
        settings.save()

        # Now entitled
        entitled, _ = FeatureService.is_feature_entitled(store, 'social.auto_publish')
        assert entitled is True

    def test_dependency_management_and_missing_prerequisites(self, setup_store):
        """Verifies that child features cannot be active if prerequisite features are disabled"""
        store = setup_store['store']

        # Ensure parent 'social.content_calendar' is disabled
        FeatureService.toggle_feature(store, 'social.content_calendar', enable=False)

        # Checking child 'social.content_approval' which depends on 'social.content_calendar'
        allowed, code, msg = FeatureService.check_feature_access(store, 'social.content_approval')
        assert allowed is False
        assert code == "DEPENDENCY_MISSING"
        assert "تقویم بصری محتوا" in msg

        # Attempting to explicitly enable child when parent is disabled should fail with ValidationError
        with pytest.raises(Exception):
            FeatureService.toggle_feature(store, 'social.content_approval', enable=True)

        # Enable parent first
        FeatureService.toggle_feature(store, 'social.content_calendar', enable=True)

        # Now child can be enabled
        result = FeatureService.toggle_feature(store, 'social.content_approval', enable=True)
        assert result['is_active'] is True
        assert FeatureService.is_feature_active(store, 'social.content_approval') is True

    def test_feature_toggle_and_data_preservation(self, setup_store):
        """Verifies that disabling a feature never deletes or corrupts database records"""
        store = setup_store['store']
        owner = setup_store['owner']

        # Create category and task while feature is active
        cat = TaskCategory.objects.create(store=store, name="بسته‌بندی سفارشات")
        task = Task.objects.create(
            store=store,
            title="آماده‌سازی سفارش شماره ۱۰۲",
            category=cat,
            creator=owner,
            status=TaskStatus.TODO
        )

        task_id = task.id
        assert Task.objects.filter(id=task_id).exists()

        # Disable tasks feature
        FeatureService.toggle_feature(store, 'tasks.planner', enable=False)
        assert FeatureService.is_feature_active(store, 'tasks.planner') is False

        # Verify records STILL EXIST in the database without any deletion
        rechecked_task = Task.objects.filter(id=task_id).first()
        assert rechecked_task is not None
        assert rechecked_task.title == "آماده‌سازی سفارش شماره ۱۰۲"
        assert TaskCategory.objects.filter(id=cat.id).exists()

        # Re-enable feature
        FeatureService.toggle_feature(store, 'tasks.planner', enable=True)
        assert FeatureService.is_feature_active(store, 'tasks.planner') is True
        assert Task.objects.get(id=task_id).status == TaskStatus.TODO

    def test_requires_feature_permission_on_api(self, setup_store):
        """Verifies that API endpoints enforce feature availability via RequiresFeature"""
        client = setup_store['owner_client']
        store = setup_store['store']

        # 1. Feature is active: API returns 200
        res = client.get('/api/v1/tasks/tasks/')
        assert res.status_code == status.HTTP_200_OK

        # 2. Disable feature: API returns 403 Forbidden with FEATURE_DISABLED
        FeatureService.toggle_feature(store, 'tasks.planner', enable=False)
        res = client.get('/api/v1/tasks/tasks/')
        assert res.status_code == status.HTTP_403_FORBIDDEN
        data = res.json()
        assert data.get('code') == 'FEATURE_DISABLED'
        assert data.get('feature') == 'tasks.planner'

        # 3. Re-enable feature: API returns 200 again
        FeatureService.toggle_feature(store, 'tasks.planner', enable=True)
        res = client.get('/api/v1/tasks/tasks/')
        assert res.status_code == status.HTTP_200_OK

    def test_social_analytics_isolation_from_core_orders(self, setup_store):
        """Verifies that disabling social analytics does not block order or inventory operations"""
        client = setup_store['owner_client']
        store = setup_store['store']

        # Disable social analytics
        FeatureService.toggle_feature(store, 'social.analytics', enable=False)

        # Analytics endpoint is blocked
        res_analytics = client.get('/api/v1/social/analytics/summary/')
        assert res_analytics.status_code == status.HTTP_403_FORBIDDEN
        assert res_analytics.json().get('code') == 'FEATURE_DISABLED'

        # But core operations continue to function normally
        product = Product.objects.create(
            store=store,
            name="کفش مردانه چرم تبریز",
            description="محصول باکیفیت"
        )
        assert Product.objects.filter(store=store, name="کفش مردانه چرم تبریز").exists()

        # Core orders API query succeeds
        res_orders = client.get('/api/v1/orders/')
        assert res_orders.status_code in [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT]

    def test_ai_provider_degradation_and_heuristic_fallback(self, setup_store):
        """Verifies that AI provider degradation falls back gracefully without crashing"""
        store = setup_store['store']
        adapter = AIProviderIntegrationAdapter()

        # When connected
        caption = adapter.generate_caption(store, product_title="کفش چرم طبیعی تبریز")
        assert "کفش چرم طبیعی تبریز" in caption
        assert len(caption) > 10

        # Simulate AI provider disabled in store feature settings
        settings = setup_store['settings']
        settings.integration_states = {'ai_provider': IntegrationState.DISABLED_BY_STORE}
        settings.save()

        # Should not raise exception; must return clean fallback template
        fallback_caption = adapter.generate_caption(store, product_title="کفش چرم طبیعی تبریز")
        assert "معرفی محصول جدید: کفش چرم طبیعی تبریز" in fallback_caption
        assert "کیفیت عالی" in fallback_caption

    def test_instagram_adapter_resilience(self, setup_store):
        """Verifies that Instagram adapter reports health cleanly even if account is not connected"""
        store = setup_store['store']
        adapter = InstagramIntegrationAdapter()

        # No instagram account connected
        health = adapter.health_check(store)
        assert health.state == IntegrationState.NOT_CONFIGURED
        assert health.details is not None
        assert "متصل نشده است" in health.message

        # Manual calendar endpoint still works when Instagram API is disconnected
        client = setup_store['owner_client']
        res = client.get('/api/v1/social/content/calendar/')
        assert res.status_code == status.HTTP_200_OK

    def test_sms_adapter_resilience(self, setup_store):
        """Verifies that SMS gateway does not raise uncaught exceptions on notifications"""
        store = setup_store['store']
        adapter = SMSGatewayIntegrationAdapter()

        # Safe non-blocking execution
        sent = adapter.send_notification(store, phone_number="09120000000", text="سفارش شما ارسال شد")
        assert sent is True

    def test_feature_settings_api_catalog_and_toggle(self, setup_store):
        """Verifies the REST API endpoints for catalog inspection, toggling, and tier update"""
        owner_client = setup_store['owner_client']
        staff_client = setup_store['staff_client']
        store = setup_store['store']

        # 1. Catalog endpoint
        res = owner_client.get('/api/v1/features/catalog/')
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert 'tier' in data
        assert 'features' in data
        assert len(data['features']) > 5

        # Check structure of a feature entry
        catalog_feat = next(f for f in data['features'] if f['key'] == 'tasks.planner')
        assert catalog_feat['is_active'] is True
        assert catalog_feat['category'] == 'OPERATIONS'

        # 2. Toggle endpoint by Owner
        res_toggle = owner_client.post('/api/v1/features/toggle/', {
            'feature': 'tasks.planner',
            'enabled': False
        })
        assert res_toggle.status_code == status.HTTP_200_OK
        assert res_toggle.json()['is_active'] is False

        # 3. Staff without owner role should be denied from toggling features
        res_staff_toggle = staff_client.post('/api/v1/features/toggle/', {
            'feature': 'tasks.planner',
            'enabled': True
        })
        assert res_staff_toggle.status_code == status.HTTP_403_FORBIDDEN

        # 4. Attempt to toggle a core feature should return 400 Bad Request
        res_core_toggle = owner_client.post('/api/v1/features/toggle/', {
            'feature': 'core.orders',
            'enabled': False
        })
        assert res_core_toggle.status_code == status.HTTP_400_BAD_REQUEST

        # 5. Tier update endpoint (with verified invoice reference)
        from apps.features.models import SubscriptionInvoice, InvoiceStatus
        SubscriptionInvoice.objects.create(
            store=store,
            tier=SubscriptionTier.ENTERPRISE,
            amount=Decimal('1490000'),
            status=InvoiceStatus.PAID,
            payment_reference='INV-SUB-PAID-001'
        )
        res_tier = owner_client.post('/api/v1/features/tier/', {
            'tier': SubscriptionTier.ENTERPRISE,
            'payment_reference': 'INV-SUB-PAID-001'
        })
        assert res_tier.status_code == status.HTTP_200_OK
        assert res_tier.json()['tier'] == SubscriptionTier.ENTERPRISE

        # 6. Integrations overview endpoint
        res_integ = owner_client.get('/api/v1/features/integrations/')
        assert res_integ.status_code == status.HTTP_200_OK
        integ_data = res_integ.json()
        assert 'instagram' in integ_data
        assert 'ai_provider' in integ_data
        assert 'sms_gateway' in integ_data
