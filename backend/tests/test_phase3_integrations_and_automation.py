import json
import pytest
from unittest.mock import patch, MagicMock
import urllib.error
from decimal import Decimal

from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.tenancy.models import Business, Store, StoreMembership, Role, MembershipStatus
from apps.social.models import (
    SocialAccount,
    SocialContent,
    SocialPlatform,
    ContentType,
    ContentStatus,
    PublishingMode,
)
from apps.social.services import SocialService
from apps.features.models import IntegrationState, StoreFeatureSetting
from apps.features.adapters import SMSGatewayIntegrationAdapter, IntegrationRegistry
from apps.automation.models import AutomationRule, AutomationExecutionLog, TriggerEvent, ExecutionStatus
from apps.automation.services import trigger_automation, execute_actions


@pytest.mark.django_db
class TestPhase3IntegrationsAndAutomation:
    @pytest.fixture
    def setup_data(self):
        owner = User.objects.create_user(email="owner_p3@test.com", password="password123", full_name="Owner P3")
        creator = User.objects.create_user(email="creator_p3@test.com", password="password123", full_name="Creator P3")
        manager = User.objects.create_user(email="manager_p3@test.com", password="password123", full_name="Manager P3")

        biz = Business.objects.create(name="Business P3", owner=owner)
        store = Store.objects.create(business=biz, name="Store P3")

        StoreMembership.objects.create(store=store, user=owner, role=Role.OWNER, status=MembershipStatus.ACTIVE)
        StoreMembership.objects.create(store=store, user=creator, role=Role.CONTENT_CREATOR, status=MembershipStatus.ACTIVE)
        StoreMembership.objects.create(store=store, user=manager, role=Role.SOCIAL_MEDIA_MANAGER, status=MembershipStatus.ACTIVE)

        account = SocialAccount.objects.create(
            store=store,
            platform=SocialPlatform.TELEGRAM,
            handle="@shoppilot_channel",
            is_connected=True
        )

        StoreFeatureSetting.objects.create(
            store=store,
            tier='PRO',
            enabled_features=['social.content_calendar']
        )

        return {
            'owner': owner,
            'creator': creator,
            'manager': manager,
            'store': store,
            'account': account,
        }

    # -------------------------------------------------------------
    # 1. Honest Social Publishing & Proof Separation
    # -------------------------------------------------------------
    def test_direct_api_publish_without_credentials_rejected(self, setup_data):
        """Direct API publish must not fake success when credentials are missing"""
        store = setup_data['store']
        creator = setup_data['creator']
        account = setup_data['account']

        content = SocialContent.objects.create(
            store=store,
            account=account,
            creator=creator,
            content_type=ContentType.TELEGRAM_POST,
            title="پست تلگرام تست",
            caption="توضیحات پست",
            publishing_mode=PublishingMode.DIRECT_API,
            status=ContentStatus.APPROVED
        )

        # Without TELEGRAM_BOT_TOKEN set in env, dispatch must raise ValidationError and NOT fake publish
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValidationError) as exc:
                SocialService.dispatch_direct_api_publish(content, user=creator)
            assert "NOT_CONFIGURED" in str(exc.value)

        content.refresh_from_db()
        assert content.status == ContentStatus.APPROVED
        assert not content.published_url

    def test_manual_reminder_mode_enforces_proof_submission_and_independent_verification(self, setup_data):
        """Manual reminder mode cannot be directly published via publish endpoint without proof"""
        store = setup_data['store']
        creator = setup_data['creator']
        manager = setup_data['manager']
        account = setup_data['account']

        content = SocialContent.objects.create(
            store=store,
            account=account,
            creator=creator,
            content_type=ContentType.POST,
            title="پست دستی بدون مدرک",
            publishing_mode=PublishingMode.MANUAL_REMINDER,
            status=ContentStatus.APPROVED
        )

        client = APIClient()
        client.force_authenticate(user=manager)
        client.credentials(HTTP_X_STORE_ID=str(store.id))

        # Attempt to call publish directly on MANUAL_REMINDER content without evidence
        res = client.post(f"/api/v1/social/content/{content.id}/publish/", {})
        assert res.status_code == 400
        assert "مدرک" in str(res.data)

        # 1. Creator submits proof -> becomes PENDING_PROOF_VERIFICATION
        submit_res = client.post(f"/api/v1/social/content/{content.id}/submit-proof/", {
            "proof_url": "https://t.me/shoppilot_channel/100"
        })
        assert submit_res.status_code == 200
        content.refresh_from_db()
        assert content.status == ContentStatus.PENDING_PROOF_VERIFICATION

        # 2. Manager independently verifies proof -> becomes PUBLISHED
        verify_res = client.post(f"/api/v1/social/content/{content.id}/verify-proof/", {
            "approved": True,
            "notes": "مدرک بررسی و تایید شد"
        })
        assert verify_res.status_code == 200
        content.refresh_from_db()
        assert content.status == ContentStatus.PUBLISHED
        assert content.published_url == "https://t.me/shoppilot_channel/100"

    # -------------------------------------------------------------
    # 2. SMS Gateway Schema Validation & Honest Status
    # -------------------------------------------------------------
    def test_sms_gateway_kavenegar_schema_success(self):
        adapter = SMSGatewayIntegrationAdapter()
        mock_cm = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({
            "return": {"status": 200, "message": "تایید شد"},
            "entries": [{"messageid": 987654321, "status": 1, "statustext": "در صف ارسال"}]
        }).encode('utf-8')
        mock_cm.__enter__.return_value = mock_response

        with patch.dict('os.environ', {'KAVENEGAR_API_KEY': 'test_api_key'}):
            with patch('urllib.request.urlopen', return_value=mock_cm):
                res = adapter.send_sms(to="09121112233", message="پیامک تستی")

        assert res['status'] == 'ACCEPTED'
        assert res['message_id'] == '987654321'
        assert '0912****233' in res['recipient']
        assert res['status'] != 'DELIVERED'  # Gateway queues it, does not fake delivered

    def test_sms_gateway_kavenegar_schema_failure(self):
        """When HTTP is 200 but Kavenegar return.status is not 200 (e.g. 411 invalid receptor)"""
        adapter = SMSGatewayIntegrationAdapter()
        mock_cm = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({
            "return": {"status": 411, "message": "گیرنده نامعتبر است"},
            "entries": None
        }).encode('utf-8')
        mock_cm.__enter__.return_value = mock_response

        with patch.dict('os.environ', {'KAVENEGAR_API_KEY': 'test_api_key'}):
            with patch('urllib.request.urlopen', return_value=mock_cm):
                res = adapter.send_sms(to="09120000000", message="پیامک تستی")

        assert res['status'] == 'FAILED'
        assert "411" in res['error']

    def test_sms_gateway_not_configured(self):
        adapter = SMSGatewayIntegrationAdapter()
        with patch.dict('os.environ', {}, clear=True):
            res = adapter.send_sms(to="09121112233", message="پیامک")
        assert res['status'] == 'NOT_CONFIGURED'

    # -------------------------------------------------------------
    # 3. Automation Failure Reflection in Execution Logs
    # -------------------------------------------------------------
    def test_automation_sms_failure_logs_as_failed(self, setup_data):
        """If SMS sending fails or is not configured, automation log status must be FAILED, not SUCCESS"""
        store = setup_data['store']

        rule = AutomationRule.objects.create(
            store=store,
            name="ارسال پیامک تبریک",
            trigger=TriggerEvent.NEW_CUSTOMER,
            actions=[{'type': 'SEND_SMS', 'template': 'خوش آمدید'}]
        )

        with patch.dict('os.environ', {}, clear=True):
            executed = trigger_automation(
                store=store,
                trigger_event=TriggerEvent.NEW_CUSTOMER,
                payload={'customer_phone': '09123334455'}
            )

        assert executed == 0  # Did not complete successfully
        log = AutomationExecutionLog.objects.filter(rule=rule).latest('id')
        assert log.status == ExecutionStatus.FAILED
        assert "NOT_CONFIGURED" in log.details or "شکست خورد" in log.details

    # -------------------------------------------------------------
    # 4. Feature Integration Config & Credentials
    # -------------------------------------------------------------
    def test_integration_config_persists_credentials_and_sanitizes_response(self, setup_data):
        store = setup_data['store']
        owner = setup_data['owner']

        client = APIClient()
        client.force_authenticate(user=owner)
        client.credentials(HTTP_X_STORE_ID=str(store.id))

        # Submit credentials for SMS gateway
        res = client.post("/api/v1/features/integrations/config/", {
            "name": "sms_gateway",
            "state": "CONFIGURED",
            "credentials": {"api_key": "secret_sms_token_12345"}
        }, format='json')

        assert res.status_code == 200
        assert res.data['name'] == 'sms_gateway'
        assert res.data['state'] == 'CONFIGURED'
        # Secret API key must NEVER be leaked in response
        assert "secret_sms_token_12345" not in json.dumps(res.data)

        # Verify key was persisted in store settings feature_configs
        setting = StoreFeatureSetting.objects.get(store=store)
        assert setting.feature_configs.get('sms_api_key') == "secret_sms_token_12345"
        assert setting.integration_states.get('sms_gateway') == 'CONFIGURED'

    def test_integration_cannot_force_connected_without_passing_health_check(self, setup_data):
        store = setup_data['store']
        owner = setup_data['owner']

        client = APIClient()
        client.force_authenticate(user=owner)
        client.credentials(HTTP_X_STORE_ID=str(store.id))

        # Try to set ai_provider to CONNECTED without any GEMINI_API_KEY
        with patch.dict('os.environ', {}, clear=True):
            res = client.post("/api/v1/features/integrations/config/", {
                "name": "ai_provider",
                "state": "CONNECTED"
            }, format='json')

        assert res.status_code == 400
        assert "امکان تغییر وضعیت به CONNECTED وجود ندارد" in str(res.data)
