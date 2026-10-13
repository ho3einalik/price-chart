from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    WarehouseViewSet, InventoryBalanceViewSet,
    InventoryMovementViewSet, StockAdjustmentAPIView, StockTransferAPIView, ReorderSuggestionsAPIView
)

router = DefaultRouter()
router.register('warehouses', WarehouseViewSet, basename='warehouse')
router.register('balances', InventoryBalanceViewSet, basename='inventory-balance')
router.register('movements', InventoryMovementViewSet, basename='inventory-movement')

urlpatterns = [
    path('adjustments/', StockAdjustmentAPIView.as_view(), name='inventory-adjustments'),
    path('transfers/', StockTransferAPIView.as_view(), name='inventory-transfers'),
    path('reorder-suggestions/', ReorderSuggestionsAPIView.as_view(), name='inventory-reorder-suggestions'),
    path('', include(router.urls)),
]
