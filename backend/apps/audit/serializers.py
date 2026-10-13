from rest_framework import serializers
from .models import AuditLog, Notification, NotificationPreference

class AuditLogSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source='user.email', read_only=True, default='')
    user_name = serializers.CharField(source='user.full_name', read_only=True, default='')

    class Meta:
        model = AuditLog
        fields = [
            'id', 'store', 'user', 'user_email', 'user_name',
            'action', 'target_type', 'target_id',
            'ip_address', 'changes', 'created_at'
        ]
        read_only_fields = fields


class NotificationSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    level_display = serializers.CharField(source='get_level_display', read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id', 'store', 'user', 'title', 'message',
            'category', 'category_display',
            'level', 'level_display',
            'is_read', 'action_url', 'created_at'
        ]
        read_only_fields = ['id', 'store', 'created_at']


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            'id', 'order_alerts', 'inventory_low_stock',
            'payment_alerts', 'social_messages',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
