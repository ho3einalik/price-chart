from django.urls import path
from .views import (
    FeatureCatalogView,
    FeatureToggleView,
    SubscriptionTierView,
    IntegrationListView,
    IntegrationConfigView
)

urlpatterns = [
    path('catalog/', FeatureCatalogView.as_view(), name='feature-catalog'),
    path('toggle/', FeatureToggleView.as_view(), name='feature-toggle'),
    path('tier/', SubscriptionTierView.as_view(), name='feature-tier'),
    path('integrations/', IntegrationListView.as_view(), name='feature-integrations'),
    path('integrations/configure/', IntegrationConfigView.as_view(), name='feature-integration-configure'),
]
