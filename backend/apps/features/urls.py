from django.urls import path
from .views import (
    FeatureCatalogView,
    FeatureToggleView,
    SubscriptionTierView,
    IntegrationListView,
    IntegrationConfigView,
    SubscriptionInvoiceListView,
    SubscriptionInvoicePayView,
    SubscriptionInvoiceCheckoutView,
    SubscriptionInvoiceVerifyView,
    SubscriptionInvoiceManualApproveView
)

urlpatterns = [
    path('catalog/', FeatureCatalogView.as_view(), name='feature-catalog'),
    path('toggle/', FeatureToggleView.as_view(), name='feature-toggle'),
    path('tier/', SubscriptionTierView.as_view(), name='feature-tier'),
    path('invoices/', SubscriptionInvoiceListView.as_view(), name='feature-invoices'),
    path('invoices/verify/', SubscriptionInvoiceVerifyView.as_view(), name='feature-invoice-verify'),
    path('invoices/<uuid:pk>/checkout/', SubscriptionInvoiceCheckoutView.as_view(), name='feature-invoice-checkout'),
    path('invoices/<uuid:pk>/pay/', SubscriptionInvoicePayView.as_view(), name='feature-invoice-pay'),
    path('invoices/<uuid:pk>/manual-approve/', SubscriptionInvoiceManualApproveView.as_view(), name='feature-invoice-manual-approve'),
    path('integrations/', IntegrationListView.as_view(), name='feature-integrations'),
    path('integrations/configure/', IntegrationConfigView.as_view(), name='feature-integration-configure'),
]

