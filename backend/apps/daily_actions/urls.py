from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DailyActionViewSet

router = DefaultRouter()
router.register('', DailyActionViewSet, basename='daily-action')

urlpatterns = [
    path('', include(router.urls)),
]
