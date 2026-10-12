from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PaymentTransactionViewSet

router = DefaultRouter()
router.register('', PaymentTransactionViewSet, basename='payment')

urlpatterns = [
    path('', include(router.urls)),
]
