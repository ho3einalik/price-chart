from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CustomerProfileViewSet

router = DefaultRouter()
router.register(r'profiles', CustomerProfileViewSet, basename='customer-profile')

urlpatterns = [
    path('', include(router.urls)),
]
