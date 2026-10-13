from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SocialAccountViewSet,
    SocialCampaignViewSet,
    SocialContentViewSet,
    SocialAnalyticsView,
    TeamSocialPerformanceView
)

router = DefaultRouter()
router.register(r'accounts', SocialAccountViewSet, basename='social-account')
router.register(r'campaigns', SocialCampaignViewSet, basename='social-campaign')
router.register(r'content', SocialContentViewSet, basename='social-content')

urlpatterns = [
    path('analytics/summary/', SocialAnalyticsView.as_view(), name='social-analytics-summary'),
    path('team-performance/', TeamSocialPerformanceView.as_view(), name='social-team-performance'),
    path('', include(router.urls)),
]
