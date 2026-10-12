from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrderViewSet, CustomerViewSet

router = DefaultRouter()
router.register('customers', CustomerViewSet, basename='customer')
router.register('', OrderViewSet, basename='order')

urlpatterns = [
    path('', include(router.urls)),
]
