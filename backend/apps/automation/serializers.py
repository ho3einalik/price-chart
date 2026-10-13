from rest_framework import serializers
from .models import AutomationRule, AutomationExecutionLog

class AutomationExecutionLogSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = AutomationExecutionLog
        fields = ['id', 'trigger_event', 'event_payload', 'status', 'status_display', 'details', 'created_at']
        read_only_fields = ['id', 'created_at']


class AutomationRuleSerializer(serializers.ModelSerializer):
    trigger_display = serializers.CharField(source='get_trigger_display', read_only=True)
    logs = AutomationExecutionLogSerializer(many=True, read_only=True)

    class Meta:
        model = AutomationRule
        fields = [
            'id', 'name', 'description', 'trigger', 'trigger_display',
            'conditions', 'actions', 'is_active', 'execution_count',
            'last_executed_at', 'logs', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'execution_count', 'last_executed_at', 'created_at', 'updated_at']
