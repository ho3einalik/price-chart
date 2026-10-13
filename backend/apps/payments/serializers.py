from rest_framework import serializers
from .models import PaymentTransaction, PaymentMethod, PaymentVerificationStatus

class PaymentTransactionSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    customer_name = serializers.CharField(source='order.customer.full_name', read_only=True)
    method_display = serializers.CharField(source='get_method_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    verified_by_name = serializers.CharField(source='verified_by.full_name', read_only=True)

    class Meta:
        model = PaymentTransaction
        fields = [
            'id', 'order', 'order_number', 'customer_name',
            'method', 'method_display', 'amount', 'refunded_amount', 'currency',
            'status', 'status_display', 'reference_number',
            'tracking_code', 'payer_card_mask', 'receipt_image_url',
            'verified_by_name', 'verified_at', 'rejection_reason',
            'created_at'
        ]
        read_only_fields = ['id', 'order_number', 'customer_name', 'method_display', 'status_display', 'verified_by_name', 'verified_at', 'refunded_amount', 'created_at']

from decimal import Decimal

class CreatePaymentInputSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()
    method = serializers.ChoiceField(choices=PaymentMethod.choices, default=PaymentMethod.CARD_TO_CARD)
    amount = serializers.DecimalField(max_digits=14, decimal_places=0, min_value=Decimal('1'))
    reference_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    tracking_code = serializers.CharField(max_length=100, required=False, allow_blank=True)
    payer_card_mask = serializers.CharField(max_length=20, required=False, allow_blank=True)
    receipt_image_url = serializers.URLField(max_length=1000, required=False, allow_blank=True)

    def validate_amount(self, value):
        if value <= Decimal('0'):
            raise serializers.ValidationError("مبلغ پرداخت باید بزرگتر از صفر باشد.")
        return value

class RejectPaymentInputSerializer(serializers.Serializer):
    reason = serializers.CharField(required=True)
