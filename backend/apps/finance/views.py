import csv
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.http import HttpResponse
from django.db.models import Sum
from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Expense, ExpenseCategory, GatewaySettlement, AccountsPayableReceivable, RefundRecord, DebtStatus, RefundStatus
from .serializers import (
    ExpenseSerializer,
    GatewaySettlementSerializer,
    AccountsPayableReceivableSerializer,
    RefundRecordSerializer
)
from apps.orders.models import Order, OrderItem, OrderStatus, PaymentStatus
from apps.tenancy.permissions import IsStoreMemberPermission

class ExpenseViewSet(viewsets.ModelViewSet):
    serializer_class = ExpenseSerializer
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]

    def get_queryset(self):
        store = getattr(self.request, 'store', None)
        if not store:
            return Expense.objects.none()
        qs = Expense.objects.filter(store=store)
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)
        return qs

    def perform_create(self, serializer):
        serializer.save(store=self.request.store, created_by=self.request.user)


class GatewaySettlementViewSet(viewsets.ModelViewSet):
    serializer_class = GatewaySettlementSerializer
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]

    def get_queryset(self):
        store = getattr(self.request, 'store', None)
        if not store:
            return GatewaySettlement.objects.none()
        return GatewaySettlement.objects.filter(store=store)

    def perform_create(self, serializer):
        serializer.save(store=self.request.store)


class AccountsPayableReceivableViewSet(viewsets.ModelViewSet):
    serializer_class = AccountsPayableReceivableSerializer
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]

    def get_queryset(self):
        store = getattr(self.request, 'store', None)
        if not store:
            return AccountsPayableReceivable.objects.none()
        qs = AccountsPayableReceivable.objects.filter(store=store).select_related('supplier', 'customer')
        entity_type = self.request.query_params.get('entity_type')
        if entity_type:
            qs = qs.filter(entity_type=entity_type)
        return qs

    def perform_create(self, serializer):
        serializer.save(store=self.request.store)

    @action(detail=True, methods=['post'], url_path='pay')
    def record_payment(self, request, pk=None):
        debt = self.get_object()
        payment_amount = Decimal(str(request.data.get('amount', 0)))
        debt.paid_amount += payment_amount
        if debt.paid_amount >= debt.total_amount:
            debt.status = DebtStatus.SETTLED
        elif debt.paid_amount > 0:
            debt.status = DebtStatus.PARTIALLY_PAID
        debt.save(update_fields=['paid_amount', 'status'])
        return Response(AccountsPayableReceivableSerializer(debt).data)


class RefundRecordViewSet(viewsets.ModelViewSet):
    serializer_class = RefundRecordSerializer
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]

    def get_queryset(self):
        store = getattr(self.request, 'store', None)
        if not store:
            return RefundRecord.objects.none()
        return RefundRecord.objects.filter(store=store).select_related('order', 'order__customer')

    def perform_create(self, serializer):
        serializer.save(store=self.request.store, processed_by=self.request.user)


class FinancialStatementView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]

    def get(self, request):
        store = request.store
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)

        # Orders revenue & COGS in period
        eligible_orders = Order.objects.filter(
            store=store,
            created_at__gte=start_date
        ).exclude(order_status=OrderStatus.CANCELLED)

        gross_sales = Decimal('0')
        discounts = Decimal('0')
        shipping_collected = Decimal('0')
        for o in eligible_orders:
            gross_sales += o.total_items_price
            discounts += o.discount_amount
            shipping_collected += o.shipping_cost

        net_sales = gross_sales - discounts

        # Calculate exact COGS from historical item snapshots
        order_items = OrderItem.objects.filter(order__in=eligible_orders)
        total_cogs = Decimal('0')
        for item in order_items:
            total_cogs += item.cost_price_snapshot * item.quantity

        gross_profit = net_sales - total_cogs
        gross_margin_pct = (gross_profit / net_sales * 100) if net_sales > 0 else Decimal('0')

        # Operating expenses in period
        expenses = Expense.objects.filter(
            store=store,
            incurred_at__gte=start_date.date()
        )
        total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')

        # Expenses by category
        expenses_breakdown = []
        expenses_by_category_dict = {}
        for cat_code, cat_name in ExpenseCategory.choices:
            cat_sum = expenses.filter(category=cat_code).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            if cat_sum > 0:
                share_pct = (cat_sum / total_expenses * 100) if total_expenses > 0 else Decimal('0')
                expenses_breakdown.append({
                    'category': cat_code,
                    'category_display': cat_name,
                    'amount': str(cat_sum),
                    'share_percentage': round(float(share_pct), 1)
                })
                expenses_by_category_dict[cat_code] = float(cat_sum)

        net_operating_profit = gross_profit - total_expenses
        net_margin_pct = (net_operating_profit / net_sales * 100) if net_sales > 0 else Decimal('0')

        return Response({
            'period_days': days,
            'currency': store.currency,
            'orders_count': eligible_orders.count(),
            # Flattened top-level numbers for direct UI access
            'gross_sales': float(gross_sales),
            'total_discounts': float(discounts),
            'net_sales': float(net_sales),
            'cogs': float(total_cogs),
            'gross_profit': float(gross_profit),
            'gross_margin_percent': round(float(gross_margin_pct), 1),
            'total_operating_expenses': float(total_expenses),
            'net_operating_profit': float(net_operating_profit),
            'net_margin_percent': round(float(net_margin_pct), 1),
            'expenses_by_category': expenses_by_category_dict,
            # Structured breakdown
            'revenue': {
                'gross_sales': str(gross_sales),
                'discounts': str(discounts),
                'shipping_collected': str(shipping_collected),
                'net_sales': str(net_sales),
            },
            'cogs_details': {
                'total_cogs': str(total_cogs),
                'gross_profit': str(gross_profit),
                'gross_margin_percentage': round(float(gross_margin_pct), 1),
            },
            'operating_expenses': {
                'total_expenses': str(total_expenses),
                'breakdown': expenses_breakdown,
            },
            'net_profit': {
                'net_operating_profit': str(net_operating_profit),
                'net_margin_percentage': round(float(net_margin_pct), 1),
                'is_profitable': net_operating_profit > 0,
            }
        })


class FinancialExportCSVView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]

    def get(self, request):
        store = request.store
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="financial_statement_{store.slug}_{days}d.csv"'
        response.write('\ufeff')  # UTF-8 BOM for Excel compatibility

        writer = csv.writer(response)
        writer.writerow(['ردیف', 'شاخص مالی', 'مقدار (تومان)', 'توضیحات'])

        eligible_orders = Order.objects.filter(store=store, created_at__gte=start_date).exclude(order_status=OrderStatus.CANCELLED)
        gross_sales = sum(o.total_items_price for o in eligible_orders)
        discounts = sum(o.discount_amount for o in eligible_orders)
        net_sales = gross_sales - discounts

        order_items = OrderItem.objects.filter(order__in=eligible_orders)
        total_cogs = sum(item.cost_price_snapshot * item.quantity for item in order_items)
        gross_profit = net_sales - total_cogs

        expenses = Expense.objects.filter(store=store, incurred_at__gte=start_date.date())
        total_opex = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        net_profit = gross_profit - total_opex

        writer.writerow(['۱', 'فروش ناخالص (Gross Sales)', int(gross_sales), f'تعداد {eligible_orders.count()} سفارش'])
        writer.writerow(['۲', 'تخفیفات اعطا شده', int(discounts), 'کوپن‌ها و تخفیفات'])
        writer.writerow(['۳', 'فروش خالص (Net Sales)', int(net_sales), 'فروش ناخالص منهای تخفیف'])
        writer.writerow(['۴', 'بهای تمام‌شده کالاها (COGS)', int(total_cogs), 'قیمت خرید کالاهای فروخته‌شده'])
        writer.writerow(['۵', 'سود ناخالص (Gross Profit)', int(gross_profit), 'فروش خالص منهای بهای خرید'])
        writer.writerow(['۶', 'هزینه‌های جاری عملیاتی (Opex)', int(total_opex), 'اجاره، حقوق، تبلیغات و بسته‌بندی'])
        writer.writerow(['۷', 'سود خالص عملیاتی (Net Profit)', int(net_profit), 'سود ناخالص منهای هزینه‌های جاری'])

        return response
