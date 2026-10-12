from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    B2BClientProfileViewSet,
    VolumeTierDiscountViewSet,
    POSTerminalViewSet,
    POSRegisterSessionViewSet,
    ProformaInvoiceViewSet,
    POSQuickCheckoutView
)

router = DefaultRouter()
router.register(r'clients', B2BClientProfileViewSet, basename='wholesale-clients')
router.register(r'volume-tiers', VolumeTierDiscountViewSet, basename='wholesale-volume-tiers')
router.register(r'terminals', POSTerminalViewSet, basename='pos-terminals')
router.register(r'sessions', POSRegisterSessionViewSet, basename='pos-sessions')
router.register(r'proformas', ProformaInvoiceViewSet, basename='wholesale-proformas')

urlpatterns = [
    path('pos/checkout/', POSQuickCheckoutView.as_view(), name='pos-quick-checkout'),
    path('', include(router.urls)),
]
