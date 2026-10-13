from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DemandForecastView,
    SlowMoversView,
    OrderRiskView,
    AICopilotView,
    CustomerFeedbackViewSet,
    CompetitorPriceTrackViewSet
)

router = DefaultRouter()
router.register(r'feedback', CustomerFeedbackViewSet, basename='intelligence-feedback')
router.register(r'competitor-prices', CompetitorPriceTrackViewSet, basename='intelligence-competitor-prices')

urlpatterns = [
    path('forecasts/', DemandForecastView.as_view(), name='demand-forecasts'),
    path('slow-movers/', SlowMoversView.as_view(), name='slow-movers'),
    path('order-risk/<uuid:order_id>/', OrderRiskView.as_view(), name='order-risk'),
    path('copilot/', AICopilotView.as_view(), name='ai-copilot'),
    path('', include(router.urls)),
]
