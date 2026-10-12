from rest_framework import serializers
from .models import DailyAction, ActionStatus

class DailyActionSerializer(serializers.ModelSerializer):
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.full_name', read_only=True)

    class Meta:
        model = DailyAction
        fields = [
            'id', 'action_key', 'title', 'explanation',
            'severity', 'severity_display', 'status', 'status_display',
            'suggested_action', 'evidence', 'assigned_to_name',
            'resolution_note', 'resolved_at', 'created_at'
        ]
        read_only_fields = ['id', 'action_key', 'severity_display', 'status_display', 'assigned_to_name', 'created_at']

class UpdateActionStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=ActionStatus.choices)
    resolution_note = serializers.CharField(required=False, allow_blank=True)
