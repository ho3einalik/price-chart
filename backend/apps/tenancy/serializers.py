from rest_framework import serializers
from .models import Business, Store, StoreMembership, Role, TeamInvitation

class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = ['id', 'name', 'created_at']
        read_only_fields = ['id', 'created_at']

class StoreSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source='business.name', read_only=True)
    my_role = serializers.SerializerMethodField()

    class Meta:
        model = Store
        fields = ['id', 'business', 'business_name', 'name', 'currency', 'timezone', 'is_active', 'my_role', 'created_at']
        read_only_fields = ['id', 'business_name', 'my_role', 'created_at']

    def get_my_role(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            membership = obj.memberships.filter(user=request.user, is_active=True).first()
            if membership:
                return membership.role
        return None

class StoreMembershipSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    open_tasks_count = serializers.SerializerMethodField()
    completed_tasks_count = serializers.SerializerMethodField()

    class Meta:
        model = StoreMembership
        fields = [
            'id', 'store', 'user', 'user_email', 'user_name',
            'role', 'role_display', 'status', 'status_display',
            'is_active', 'custom_permissions', 'open_tasks_count',
            'completed_tasks_count', 'created_at'
        ]
        read_only_fields = ['id', 'user_email', 'user_name', 'role_display', 'status_display', 'open_tasks_count', 'completed_tasks_count', 'created_at']

    def get_open_tasks_count(self, obj):
        try:
            from apps.tasks.models import Task
            return Task.objects.filter(store=obj.store, assignee=obj.user).exclude(status__in=['COMPLETED', 'CANCELLED']).count()
        except Exception:
            return 0

    def get_completed_tasks_count(self, obj):
        try:
            from apps.tasks.models import Task
            return Task.objects.filter(store=obj.store, assignee=obj.user, status='COMPLETED').count()
        except Exception:
            return 0

class TeamInvitationSerializer(serializers.ModelSerializer):
    inviter_name = serializers.CharField(source='inviter.full_name', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = TeamInvitation
        fields = [
            'id', 'store', 'email', 'role', 'role_display',
            'inviter_name', 'token', 'status', 'status_display',
            'custom_permissions', 'created_at', 'expires_at'
        ]
        read_only_fields = ['id', 'token', 'status', 'status_display', 'inviter_name', 'created_at', 'expires_at']

class CreateInvitationInputSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=Role.choices, default=Role.CONTENT_CREATOR)
    custom_permissions = serializers.ListField(child=serializers.CharField(), required=False, default=list)

