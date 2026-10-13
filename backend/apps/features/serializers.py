from rest_framework import serializers
from .models import SubscriptionTier, IntegrationState


class FeatureItemSerializer(serializers.Serializer):
    key = serializers.CharField()
    name_fa = serializers.CharField()
    description_fa = serializers.CharField()
    category = serializers.CharField()
    is_core = serializers.BooleanField()
    is_entitled = serializers.BooleanField()
    is_active = serializers.BooleanField()
    min_tier = serializers.CharField()
    depends_on = serializers.ListField(child=serializers.CharField())
    missing_dependencies = serializers.ListField(child=serializers.CharField())
    dependents = serializers.ListField(child=serializers.CharField())
    integrations = serializers.ListField()
    impact_warning_fa = serializers.CharField(allow_blank=True)


class FeatureToggleInputSerializer(serializers.Serializer):
    feature = serializers.CharField()
    enabled = serializers.BooleanField()


class SubscriptionTierUpdateInputSerializer(serializers.Serializer):
    tier = serializers.ChoiceField(choices=SubscriptionTier.choices)
    payment_reference = serializers.CharField(required=False, allow_blank=True, default='')


class IntegrationConfigInputSerializer(serializers.Serializer):
    name = serializers.CharField()
    state = serializers.ChoiceField(choices=IntegrationState.choices)
    credentials = serializers.DictField(required=False, default=dict)


from .models import SubscriptionInvoice, InvoiceStatus

class SubscriptionInvoiceSerializer(serializers.ModelSerializer):
    tier_display = serializers.CharField(source='get_tier_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = SubscriptionInvoice
        fields = [
            'id', 'store', 'tier', 'tier_display', 'amount', 'status',
            'status_display', 'payment_reference', 'gateway_tracking_code',
            'created_at', 'paid_at'
        ]
        read_only_fields = ['id', 'store', 'status', 'created_at', 'paid_at']


class CreateInvoiceInputSerializer(serializers.Serializer):
    tier = serializers.ChoiceField(choices=SubscriptionTier.choices)
