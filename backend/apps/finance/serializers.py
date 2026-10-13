from rest_framework import serializers
from .models import Expense, GatewaySettlement, AccountsPayableReceivable, RefundRecord

class ExpenseSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = Expense
        fields = [
            'id', 'title', 'category', 'category_display', 'amount',
            'currency', 'incurred_at', 'receipt_image_url', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class GatewaySettlementSerializer(serializers.ModelSerializer):
    class Meta:
        model = GatewaySettlement
        fields = [
            'id', 'gateway_name', 'settlement_date', 'gross_amount',
            'gateway_fee', 'net_deposited_amount', 'sheba_number',
            'tracking_reference', 'is_reconciled', 'discrepancy_amount',
            'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AccountsPayableReceivableSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.company_name', read_only=True)
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    remaining_balance = serializers.DecimalField(max_digits=14, decimal_places=0, read_only=True)

    class Meta:
        model = AccountsPayableReceivable
        fields = [
            'id', 'entity_type', 'supplier', 'supplier_name', 'customer',
            'customer_name', 'title', 'total_amount', 'paid_amount',
            'remaining_balance', 'due_date', 'status', 'status_display',
            'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'remaining_balance', 'status_display', 'created_at', 'updated_at']


class RefundRecordSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    customer_name = serializers.CharField(source='order.customer.full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = RefundRecord
        fields = [
            'id', 'order', 'order_number', 'customer_name', 'amount',
            'destination_card_or_sheba', 'tracking_code', 'status',
            'status_display', 'reason', 'processed_at'
        ]
        read_only_fields = ['id', 'order_number', 'customer_name', 'status_display', 'processed_at']
