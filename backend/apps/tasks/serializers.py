from rest_framework import serializers
from apps.accounts.serializers import UserSerializer
from .models import (
    TaskCategory,
    Task,
    TaskPriority,
    TaskStatus,
    TaskChecklistItem,
    TaskComment,
    TaskActivityLog
)


class TaskCategorySerializer(serializers.ModelSerializer):
    tasks_count = serializers.IntegerField(source='tasks.count', read_only=True)

    class Meta:
        model = TaskCategory
        fields = ['id', 'name', 'color', 'icon', 'tasks_count', 'created_at']
        read_only_fields = ['id', 'tasks_count', 'created_at']


class TaskChecklistItemSerializer(serializers.ModelSerializer):
    completed_by_name = serializers.CharField(source='completed_by.full_name', read_only=True)

    class Meta:
        model = TaskChecklistItem
        fields = [
            'id', 'task', 'title', 'is_completed',
            'completed_by', 'completed_by_name', 'completed_at', 'order'
        ]
        read_only_fields = ['id', 'completed_by', 'completed_at']


class TaskCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = TaskComment
        fields = ['id', 'task', 'author', 'author_name', 'content', 'created_at']
        read_only_fields = ['id', 'author', 'created_at']

    def get_author_name(self, obj):
        return getattr(obj.author, 'full_name', '') or obj.author.email


class TaskActivityLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = TaskActivityLog
        fields = ['id', 'task', 'actor', 'actor_name', 'action_type', 'old_value', 'new_value', 'note', 'created_at']
        read_only_fields = fields

    def get_actor_name(self, obj):
        if obj.actor:
            return getattr(obj.actor, 'full_name', '') or obj.actor.email
        return "سیستم"


class TaskListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)
    category_color = serializers.CharField(source='category.color', read_only=True, default=None)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    creator_name = serializers.SerializerMethodField()
    assignee_name = serializers.SerializerMethodField()
    reviewer_name = serializers.SerializerMethodField()
    checklist_total = serializers.SerializerMethodField()
    checklist_completed = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'category', 'category_name', 'category_color',
            'priority', 'priority_display', 'status', 'status_display',
            'creator', 'creator_name', 'assignee', 'assignee_name', 'reviewer', 'reviewer_name',
            'start_date', 'due_date', 'is_overdue', 'estimated_hours', 'actual_hours',
            'requires_verification', 'completion_evidence', 'completed_at',
            'checklist_total', 'checklist_completed', 'created_at', 'updated_at'
        ]

    def get_creator_name(self, obj):
        return getattr(obj.creator, 'full_name', '') or obj.creator.email

    def get_assignee_name(self, obj):
        if obj.assignee:
            return getattr(obj.assignee, 'full_name', '') or obj.assignee.email
        return None

    def get_reviewer_name(self, obj):
        if obj.reviewer:
            return getattr(obj.reviewer, 'full_name', '') or obj.reviewer.email
        return None

    def get_checklist_total(self, obj):
        return obj.checklist_items.count()

    def get_checklist_completed(self, obj):
        return obj.checklist_items.filter(is_completed=True).count()

    def get_is_overdue(self, obj):
        from django.utils import timezone
        if obj.due_date and obj.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
            return obj.due_date < timezone.now().date()
        return False


class TaskDetailSerializer(TaskListSerializer):
    checklist_items = TaskChecklistItemSerializer(many=True, read_only=True)
    comments = TaskCommentSerializer(many=True, read_only=True)
    activity_logs = TaskActivityLogSerializer(many=True, read_only=True)
    related_product_title = serializers.CharField(source='related_product.title', read_only=True, default=None)
    related_order_number = serializers.CharField(source='related_order.order_number', read_only=True, default=None)

    class Meta(TaskListSerializer.Meta):
        fields = TaskListSerializer.Meta.fields + [
            'checklist_items', 'comments', 'activity_logs',
            'related_product', 'related_product_title',
            'related_order', 'related_order_number'
        ]


class TaskCreateUpdateSerializer(serializers.ModelSerializer):
    checklist_items = serializers.ListField(
        child=serializers.CharField(max_length=255),
        required=False,
        write_only=True
    )

    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'category', 'priority', 'status',
            'assignee', 'reviewer', 'start_date', 'due_date',
            'estimated_hours', 'actual_hours', 'requires_verification',
            'completion_evidence', 'related_product', 'related_order',
            'checklist_items'
        ]
        read_only_fields = ['id']


class TaskStatusChangeInputSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=TaskStatus.choices)
    completion_evidence = serializers.CharField(required=False, allow_blank=True)


class TaskVerificationInputSerializer(serializers.Serializer):
    approved = serializers.BooleanField(default=True)
    feedback = serializers.CharField(required=False, allow_blank=True)


class TaskCommentInputSerializer(serializers.Serializer):
    content = serializers.CharField()
