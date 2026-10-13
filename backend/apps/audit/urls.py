from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AuditLogViewSet,
    NotificationViewSet,
    NotificationPreferenceView,
    TeamActivitySummaryView,
    AuditExportCSVView
)

router = DefaultRouter()
router.register(r'logs', AuditLogViewSet, basename='audit-logs')
router.register(r'notifications', NotificationViewSet, basename='audit-notifications')

urlpatterns = [
    path('preferences/', NotificationPreferenceView.as_view(), name='notification-preferences'),
    path('team-activity/', TeamActivitySummaryView.as_view(), name='team-activity-summary'),
    path('export-csv/', AuditExportCSVView.as_view(), name='audit-export-csv'),
    path('', include(router.urls)),
]
