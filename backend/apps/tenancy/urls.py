from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BusinessViewSet, StoreViewSet, StoreMembershipViewSet

router = DefaultRouter()
router.register('businesses', BusinessViewSet, basename='business')
router.register('stores', StoreViewSet, basename='store')
router.register('memberships', StoreMembershipViewSet, basename='membership')

urlpatterns = [
    path('', include(router.urls)),
]
