from django.urls import path
from .views import OverviewAnalyticsAPIView

urlpatterns = [
    path('overview/', OverviewAnalyticsAPIView.as_view(), name='analytics-overview'),
]
