from decimal import Decimal
import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.tenancy.models import Business, Store, StoreMembership, Role, MembershipStatus
from apps.social.models import (
    SocialAccount,
    SocialCampaign,
    SocialContent,
    SocialPlatform,
    ContentType,
    ContentStatus,
    ApprovalAction,
    ContentMetricSnapshot
)
from apps.social.services import SocialService


@pytest.mark.django_db
class TestSocialOperations:
    @pytest.fixture
    def setup_social(self):
        owner = User.objects.create_user(email="social_owner@test.com", password="password123", full_name="Social Owner")
        creator = User.objects.create_user(email="social_creator@test.com", password="password123", full_name="Creator User")
        manager = User.objects.create_user(email="social_manager@test.com", password="password123", full_name="SMM Manager")

        biz = Business.objects.create(name="Social Biz", owner=owner)
        store = Store.objects.create(business=biz, name="Social Store")

        StoreMembership.objects.create(store=store, user=owner, role=Role.OWNER, status=MembershipStatus.ACTIVE)
        StoreMembership.objects.create(store=store, user=creator, role=Role.CONTENT_CREATOR, status=MembershipStatus.ACTIVE)
        StoreMembership.objects.create(store=store, user=manager, role=Role.SOCIAL_MEDIA_MANAGER, status=MembershipStatus.ACTIVE)

        account = SocialAccount.objects.create(
            store=store,
            platform=SocialPlatform.INSTAGRAM,
            handle="@shoppilot_store",
            follower_count=12500,
            is_connected=True
        )

        campaign = SocialCampaign.objects.create(
            store=store,
            name="کمپین حراج پاییزی",
            budget=Decimal("50000000"),
            status="ACTIVE"
        )

        return {
            'owner': owner,
            'creator': creator,
            'manager': manager,
            'store': store,
            'account': account,
            'campaign': campaign
        }

    def test_content_approval_lifecycle(self, setup_social):
        store = setup_social['store']
        creator = setup_social['creator']
        manager = setup_social['manager']
        account = setup_social['account']

        content = SocialContent.objects.create(
            store=store,
            account=account,
            creator=creator,
            content_type=ContentType.REEL,
            title="معرفی ۵ کالکشن برتر پاییزه",
            caption="تخفیف ویژه آغاز شد! #استایل #پاییزه",
            status=ContentStatus.IN_PRODUCTION
        )

        # 1. Submit for review
        SocialService.submit_for_review(content, user=creator)
        content.refresh_from_db()
        assert content.status == ContentStatus.READY_FOR_REVIEW
        assert content.approval_logs.filter(action=ApprovalAction.SUBMITTED).exists()

        # 2. Manager reviews & approves
        SocialService.review_content(
            content=content,
            reviewer=manager,
            action=ApprovalAction.APPROVED,
            feedback="کپشن و ادیت ویدیو عالی است."
        )
        content.refresh_from_db()
        assert content.status == ContentStatus.APPROVED

        # 3. Schedule content
        scheduled_time = timezone.now() + timezone.timedelta(days=2)
        SocialService.schedule_content(content, scheduled_at=scheduled_time, user=manager)
        content.refresh_from_db()
        assert content.status == ContentStatus.SCHEDULED
        assert content.scheduled_at == scheduled_time

        # 4. Submit proof & independent manager verification
        SocialService.submit_proof(content, proof_url="https://instagram.com/p/DB123456", user=creator)
        content.refresh_from_db()
        assert content.status == ContentStatus.PENDING_PROOF_VERIFICATION

        SocialService.verify_proof(content, manager_user=manager, approved=True)
        content.refresh_from_db()
        assert content.status == ContentStatus.PUBLISHED
        assert content.published_at is not None
        assert content.published_url == "https://instagram.com/p/DB123456"

    def test_engagement_rate_calculation(self, setup_social):
        store = setup_social['store']
        owner = setup_social['owner']
        account = setup_social['account']

        content = SocialContent.objects.create(
            store=store,
            account=account,
            creator=owner,
            content_type=ContentType.POST,
            title="پست تخفیف پایان هفته",
            status=ContentStatus.PUBLISHED
        )

        # Reach = 10,000
        # Likes = 600, Comments = 150, Shares = 100, Saves = 150 -> Total interactions = 1000
        # Formula: (1000 / 10000) * 100 = 10.00%
        snapshot = SocialService.record_metrics(
            content=content,
            metrics_data={
                'reach': 10000,
                'impressions': 14000,
                'likes': 600,
                'comments': 150,
                'shares': 100,
                'saves': 150,
                'attributed_orders_count': 12,
                'attributed_revenue': 36000000
            }
        )

        assert snapshot.engagement_rate == Decimal("10.00")
        assert snapshot.attributed_orders_count == 12
        assert snapshot.attributed_revenue == Decimal("36000000")

    def test_social_analytics_summary(self, setup_social):
        store = setup_social['store']
        owner = setup_social['owner']
        account = setup_social['account']

        content = SocialContent.objects.create(
            store=store,
            account=account,
            creator=owner,
            content_type=ContentType.REEL,
            title="ریلز تست آنالیز",
            status=ContentStatus.PUBLISHED
        )

        SocialService.record_metrics(
            content=content,
            metrics_data={
                'reach': 5000,
                'likes': 250,
                'comments': 50,
                'shares': 50,
                'saves': 50,
                'attributed_orders_count': 4,
                'attributed_revenue': 12000000
            }
        )

        summary = SocialService.get_social_analytics_summary(store=store, days=30)
        assert summary['total_published_posts'] == 1
        assert summary['total_reach'] == 5000
        assert summary['total_engagements'] == 400
        assert summary['average_engagement_rate'] == 8.0
        assert summary['total_attributed_revenue'] == Decimal("12000000")
        assert len(summary['top_posts']) == 1
