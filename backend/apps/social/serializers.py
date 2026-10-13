from rest_framework import serializers
from .models import (
    SocialAccount,
    SocialCampaign,
    SocialContent,
    ContentType,
    ContentStatus,
    ApprovalAction,
    ContentApprovalLog,
    ContentMetricSnapshot,
    MetricSource
)


class SocialAccountSerializer(serializers.ModelSerializer):
    platform_display = serializers.CharField(source='get_platform_display', read_only=True)
    connection_mode_display = serializers.CharField(source='get_connection_mode_display', read_only=True)
    contents_count = serializers.IntegerField(source='contents.count', read_only=True)

    class Meta:
        model = SocialAccount
        fields = [
            'id', 'platform', 'platform_display', 'handle', 'display_name',
            'profile_image_url', 'is_connected', 'connection_mode',
            'connection_mode_display', 'follower_count', 'bio', 'contents_count', 'created_at'
        ]
        read_only_fields = ['id', 'contents_count', 'created_at']


class SocialCampaignSerializer(serializers.ModelSerializer):
    objective_display = serializers.CharField(source='get_objective_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    contents_count = serializers.IntegerField(source='contents.count', read_only=True)

    class Meta:
        model = SocialCampaign
        fields = [
            'id', 'name', 'objective', 'objective_display', 'budget',
            'start_date', 'end_date', 'status', 'status_display',
            'description', 'contents_count', 'created_at'
        ]
        read_only_fields = ['id', 'contents_count', 'created_at']


class ContentApprovalLogSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.SerializerMethodField()
    action_display = serializers.CharField(source='get_action_display', read_only=True)

    class Meta:
        model = ContentApprovalLog
        fields = ['id', 'content', 'reviewer', 'reviewer_name', 'action', 'action_display', 'feedback', 'created_at']
        read_only_fields = fields

    def get_reviewer_name(self, obj):
        return getattr(obj.reviewer, 'full_name', '') or obj.reviewer.email


class ContentMetricSnapshotSerializer(serializers.ModelSerializer):
    source_display = serializers.CharField(source='get_source_display', read_only=True)

    class Meta:
        model = ContentMetricSnapshot
        fields = [
            'id', 'content', 'source', 'source_display', 'reach', 'impressions',
            'likes', 'comments', 'shares', 'saves', 'clicks',
            'engagement_rate', 'attributed_orders_count', 'attributed_revenue', 'recorded_at'
        ]
        read_only_fields = ['id', 'engagement_rate', 'recorded_at']


class SocialContentListSerializer(serializers.ModelSerializer):
    platform = serializers.CharField(source='account.platform', read_only=True, default=None)
    platform_display = serializers.CharField(source='account.get_platform_display', read_only=True, default=None)
    account_handle = serializers.CharField(source='account.handle', read_only=True, default=None)
    campaign_name = serializers.CharField(source='campaign.name', read_only=True, default=None)
    content_type_display = serializers.CharField(source='get_content_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    publishing_mode_display = serializers.CharField(source='get_publishing_mode_display', read_only=True)
    creator_name = serializers.SerializerMethodField()
    assignee_name = serializers.SerializerMethodField()
    latest_metrics = serializers.SerializerMethodField()

    class Meta:
        model = SocialContent
        fields = [
            'id', 'account', 'platform', 'platform_display', 'account_handle',
            'campaign', 'campaign_name', 'content_type', 'content_type_display',
            'title', 'caption', 'hashtags', 'media_urls', 'thumbnail_url',
            'status', 'status_display', 'publishing_mode', 'publishing_mode_display',
            'creator', 'creator_name', 'assignee', 'assignee_name',
            'scheduled_at', 'published_at', 'published_url', 'destination_url',
            'related_product', 'latest_metrics', 'created_at', 'updated_at'
        ]

    def get_creator_name(self, obj):
        return getattr(obj.creator, 'full_name', '') or obj.creator.email

    def get_assignee_name(self, obj):
        if obj.assignee:
            return getattr(obj.assignee, 'full_name', '') or obj.assignee.email
        return None

    def get_latest_metrics(self, obj):
        latest = obj.metric_snapshots.first()
        if latest:
            return {
                'reach': latest.reach,
                'impressions': latest.impressions,
                'likes': latest.likes,
                'comments': latest.comments,
                'saves': latest.saves,
                'shares': latest.shares,
                'engagement_rate': float(latest.engagement_rate),
                'attributed_revenue': float(latest.attributed_revenue)
            }
        return None


class SocialContentDetailSerializer(SocialContentListSerializer):
    approval_logs = ContentApprovalLogSerializer(many=True, read_only=True)
    metric_snapshots = ContentMetricSnapshotSerializer(many=True, read_only=True)
    related_product_title = serializers.CharField(source='related_product.name', read_only=True, default=None)

    class Meta(SocialContentListSerializer.Meta):
        fields = SocialContentListSerializer.Meta.fields + [
            'approval_logs', 'metric_snapshots', 'related_product_title'
        ]


class SocialContentCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialContent
        fields = [
            'id', 'account', 'campaign', 'content_type', 'title', 'caption',
            'hashtags', 'media_urls', 'thumbnail_url', 'status', 'publishing_mode',
            'assignee', 'scheduled_at', 'published_url', 'related_product', 'destination_url'
        ]
        read_only_fields = ['id']


class ContentReviewInputSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=ApprovalAction.choices)
    feedback = serializers.CharField(required=False, allow_blank=True)


class ContentScheduleInputSerializer(serializers.Serializer):
    scheduled_at = serializers.DateTimeField()


class ContentPublishInputSerializer(serializers.Serializer):
    published_url = serializers.CharField(required=False, allow_blank=True)


class RecordMetricsInputSerializer(serializers.Serializer):
    source = serializers.ChoiceField(choices=MetricSource.choices, default=MetricSource.MANUAL)
    reach = serializers.IntegerField(min_value=0, default=0)
    impressions = serializers.IntegerField(min_value=0, default=0)
    likes = serializers.IntegerField(min_value=0, default=0)
    comments = serializers.IntegerField(min_value=0, default=0)
    shares = serializers.IntegerField(min_value=0, default=0)
    saves = serializers.IntegerField(min_value=0, default=0)
    clicks = serializers.IntegerField(min_value=0, default=0)
    attributed_orders_count = serializers.IntegerField(min_value=0, default=0)
    attributed_revenue = serializers.DecimalField(max_digits=15, decimal_places=0, default=0)
