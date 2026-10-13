from django.urls import path
from .views import (
    FeatureCatalogView,
    FeatureToggleView,
    SubscriptionTierView,
    IntegrationListView,
    IntegrationConfigView,
    SubscriptionInvoiceListView,
    SubscriptionInvoicePayView
)

urlpatterns = [
    path('catalog/', FeatureCatalogView.as_view(), name='feature-catalog'),
    path('toggle/', FeatureToggleView.as_view(), name='feature-toggle'),
    path('tier/', SubscriptionTierView.as_view(), name='feature-tier'),
    path('invoices/', SubscriptionInvoiceListView.as_view(), name='feature-invoices'),
    path('invoices/<uuid:pk>/pay/', SubscriptionInvoicePayView.as_view(), name='feature-invoice-pay'),
    path('integrations/', IntegrationListView.as_view(), name='feature-integrations'),
    path('integrations/configure/', IntegrationConfigView.as_view(), name='feature-integration-configure'),
]
