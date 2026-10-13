from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ExpenseViewSet,
    FinancialStatementView,
    GatewaySettlementViewSet,
    AccountsPayableReceivableViewSet,
    RefundRecordViewSet,
    FinancialExportCSVView
)

router = DefaultRouter()
router.register(r'expenses', ExpenseViewSet, basename='expense')
router.register(r'settlements', GatewaySettlementViewSet, basename='gateway-settlement')
router.register(r'debts', AccountsPayableReceivableViewSet, basename='accounts-debt')
router.register(r'refunds', RefundRecordViewSet, basename='refund-record')

urlpatterns = [
    path('statement/', FinancialStatementView.as_view(), name='financial-statement'),
    path('export-csv/', FinancialExportCSVView.as_view(), name='financial-export-csv'),
    path('', include(router.urls)),
]
