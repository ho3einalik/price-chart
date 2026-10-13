from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Avg, Count, F, Q
from rest_framework.exceptions import ValidationError, PermissionDenied

from .models import (
    SocialContent,
    ContentStatus,
    ApprovalAction,
    ContentApprovalLog,
    ContentMetricSnapshot,
    MetricSource
)


class SocialService:
    @staticmethod
    def submit_for_review(content, user):
        old_status = content.status
        content.status = ContentStatus.READY_FOR_REVIEW
        content.save()

        user_name = getattr(user, 'full_name', '') or getattr(user, 'email', str(user))
        ContentApprovalLog.objects.create(
            content=content,
            reviewer=user,
            action=ApprovalAction.SUBMITTED,
            feedback=f"محتوا جهت بررسی و تأیید توسط {user_name} ارسال شد."
        )
        return content

    @staticmethod
    def review_content(content, reviewer, action, feedback=""):
        if action not in ApprovalAction.values:
            raise ValidationError({"action": f"عملیات بررسی نامعتبر است: {action}"})

        if action == ApprovalAction.APPROVED:
            # If already scheduled, keep SCHEDULED, otherwise APPROVED
            if content.scheduled_at and content.scheduled_at > timezone.now():
                content.status = ContentStatus.SCHEDULED
            else:
                content.status = ContentStatus.APPROVED
        elif action == ApprovalAction.CHANGES_REQUESTED:
            content.status = ContentStatus.IN_PRODUCTION
        elif action == ApprovalAction.REJECTED:
            content.status = ContentStatus.REJECTED

        content.save()

        ContentApprovalLog.objects.create(
            content=content,
            reviewer=reviewer,
            action=action,
            feedback=feedback
        )
        return content

    @staticmethod
    def schedule_content(content, scheduled_at, user):
        if not scheduled_at:
            raise ValidationError({"scheduled_at": "زمان‌بندی انتشار مشخص نشده است."})

        content.scheduled_at = scheduled_at
        # If approved or already verified, set status to SCHEDULED
        if content.status in [ContentStatus.APPROVED, ContentStatus.IDEA, ContentStatus.IN_PRODUCTION]:
            content.status = ContentStatus.SCHEDULED
        content.save()
        return content

    @staticmethod
    def publish_content(content, published_url="", user=None):
        content.status = ContentStatus.PUBLISHED
        content.published_at = timezone.now()
        if published_url:
            content.published_url = published_url
        content.save()
        return content

    @staticmethod
    def submit_proof(content, proof_url='', proof_image_url='', user=None):
        content.proof_url = proof_url
        content.proof_image_url = proof_image_url
        content.status = ContentStatus.PUBLISHED
        content.published_at = timezone.now()
        content.save(update_fields=['proof_url', 'proof_image_url', 'status', 'published_at', 'updated_at'])
        return content

    @staticmethod
    def verify_proof(content, manager_user):
        content.approved_by = manager_user
        content.save(update_fields=['approved_by', 'updated_at'])
        return content

    @staticmethod
    def record_metrics(content, metrics_data, source=MetricSource.MANUAL, user=None):
        reach = int(metrics_data.get('reach', 0))
        impressions = int(metrics_data.get('impressions', reach))
        likes = int(metrics_data.get('likes', 0))
        comments = int(metrics_data.get('comments', 0))
        shares = int(metrics_data.get('shares', 0))
        saves = int(metrics_data.get('saves', 0))
        clicks = int(metrics_data.get('clicks', 0))
        attributed_orders_count = int(metrics_data.get('attributed_orders_count', 0))
        attributed_revenue = Decimal(str(metrics_data.get('attributed_revenue', 0)))

        snapshot = ContentMetricSnapshot.objects.create(
            content=content,
            source=source,
            recorded_by=user,
            reach=reach,
            impressions=impressions,
            likes=likes,
            comments=comments,
            shares=shares,
            saves=saves,
            clicks=clicks,
            attributed_orders_count=attributed_orders_count,
            attributed_revenue=attributed_revenue
        )
        return snapshot

    @staticmethod
    def get_social_analytics_summary(store, days=30):
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        contents = SocialContent.objects.filter(store=store)

        snapshots = ContentMetricSnapshot.objects.filter(
            content__store=store,
            recorded_at__gte=cutoff_date
        )

        total_posts = contents.filter(status=ContentStatus.PUBLISHED).count()
        total_reach = snapshots.aggregate(total=Sum('reach'))['total'] or 0
        total_impressions = snapshots.aggregate(total=Sum('impressions'))['total'] or 0
        total_likes = snapshots.aggregate(total=Sum('likes'))['total'] or 0
        total_comments = snapshots.aggregate(total=Sum('comments'))['total'] or 0
        total_saves = snapshots.aggregate(total=Sum('saves'))['total'] or 0
        total_shares = snapshots.aggregate(total=Sum('shares'))['total'] or 0
        total_attributed_revenue = snapshots.aggregate(total=Sum('attributed_revenue'))['total'] or Decimal('0')
        total_attributed_orders = snapshots.aggregate(total=Sum('attributed_orders_count'))['total'] or 0

        total_engagements = total_likes + total_comments + total_saves + total_shares
        avg_engagement_rate = 0.0
        if total_reach > 0:
            avg_engagement_rate = round(float((Decimal(total_engagements) / Decimal(total_reach)) * Decimal(100)), 2)

        # Platform distribution
        by_platform = []
        for account in store.socialaccounts.all():
            account_snapshots = ContentMetricSnapshot.objects.filter(content__account=account)
            acc_reach = account_snapshots.aggregate(total=Sum('reach'))['total'] or 0
            acc_posts = account.contents.filter(status=ContentStatus.PUBLISHED).count()
            by_platform.append({
                'account_id': str(account.id),
                'platform': account.platform,
                'platform_display': account.get_platform_display(),
                'handle': account.handle,
                'follower_count': account.follower_count,
                'published_posts': acc_posts,
                'total_reach': acc_reach
            })

        # Top 5 performing posts by engagement rate
        top_snapshots = snapshots.order_by('-engagement_rate', '-reach')[:5]
        top_posts = []
        for s in top_snapshots:
            top_posts.append({
                'id': str(s.content.id),
                'title': s.content.title,
                'content_type': s.content.get_content_type_display(),
                'thumbnail_url': s.content.thumbnail_url,
                'reach': s.reach,
                'likes': s.likes,
                'comments': s.comments,
                'saves': s.saves,
                'engagement_rate': float(s.engagement_rate),
                'published_url': s.content.published_url
            })

        return {
            'period_days': days,
            'total_published_posts': total_posts,
            'total_reach': total_reach,
            'total_impressions': total_impressions,
            'total_engagements': total_engagements,
            'average_engagement_rate': avg_engagement_rate,
            'total_attributed_revenue': total_attributed_revenue,
            'total_attributed_orders': total_attributed_orders,
            'platforms': by_platform,
            'top_posts': top_posts
        }

    @staticmethod
    def get_team_performance(store, days=30):
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        members = store.memberships.select_related('user').all()
        team_stats = []

        for m in members:
            assigned_contents = SocialContent.objects.filter(
                store=store,
                assignee=m.user,
                created_at__gte=cutoff_date
            )
            published = assigned_contents.filter(status=ContentStatus.PUBLISHED).count()
            total_reach = ContentMetricSnapshot.objects.filter(
                content__in=assigned_contents
            ).aggregate(total=Sum('reach'))['total'] or 0

            team_stats.append({
                'user_id': str(m.user.id),
                'full_name': m.user.get_full_name() or m.user.email,
                'role': m.role,
                'role_display': m.get_role_display(),
                'total_assigned_contents': assigned_contents.count(),
                'published_contents': published,
                'completion_rate_percent': round((published / assigned_contents.count() * 100) if assigned_contents.count() > 0 else 100.0, 1),
                'generated_reach': total_reach
            })

        return team_stats

