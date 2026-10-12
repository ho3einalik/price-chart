from rest_framework import serializers
from .models import B2BClientProfile, VolumeTierDiscount, POSTerminal, POSRegisterSession, ProformaInvoice

class B2BClientProfileSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    customer_phone = serializers.CharField(source='customer.phone_number', read_only=True)
    tier_display = serializers.CharField(source='get_tier_display', read_only=True)
    available_credit = serializers.DecimalField(max_digits=14, decimal_places=0, read_only=True)

    class Meta:
        model = B2BClientProfile
        fields = [
            'id', 'customer', 'customer_name', 'customer_phone',
            'company_name', 'economic_code', 'credit_limit', 'current_debt',
            'available_credit', 'payment_terms_days', 'tier', 'tier_display',
            'is_approved', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'current_debt', 'available_credit', 'created_at', 'updated_at']


class VolumeTierDiscountSerializer(serializers.ModelSerializer):
    variant_sku = serializers.CharField(source='variant.sku', read_only=True)
    variant_title = serializers.CharField(source='variant.name', read_only=True)

    class Meta:
        model = VolumeTierDiscount
        fields = [
            'id', 'variant', 'variant_sku', 'variant_title',
            'min_quantity', 'unit_price', 'tier_label',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class POSTerminalSerializer(serializers.ModelSerializer):
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)

    class Meta:
        model = POSTerminal
        fields = [
            'id', 'name', 'terminal_code', 'warehouse', 'warehouse_name',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class POSRegisterSessionSerializer(serializers.ModelSerializer):
    terminal_name = serializers.CharField(source='terminal.name', read_only=True)
    opened_by_name = serializers.CharField(source='opened_by.username', read_only=True)
    closed_by_name = serializers.CharField(source='closed_by.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = POSRegisterSession
        fields = [
            'id', 'terminal', 'terminal_name',
            'opened_by', 'opened_by_name',
            'closed_by', 'closed_by_name',
            'opening_cash', 'closing_cash', 'total_sales',
            'status', 'status_display',
            'opened_at', 'closed_at', 'notes'
        ]
        read_only_fields = ['id', 'opened_by', 'closed_by', 'total_sales', 'opened_at', 'closed_at']


class ProformaInvoiceSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.company_name', read_only=True)
    client_phone = serializers.CharField(source='client.customer.phone_number', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = ProformaInvoice
        fields = [
            'id', 'invoice_number', 'client', 'client_name', 'client_phone',
            'subtotal', 'discount', 'tax', 'grand_total',
            'status', 'status_display', 'valid_until',
            'items', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
