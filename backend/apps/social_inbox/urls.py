from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ConversationThreadViewSet

router = DefaultRouter()
router.register(r'threads', ConversationThreadViewSet, basename='inbox-thread')

urlpatterns = [
    path('', include(router.urls)),
]
