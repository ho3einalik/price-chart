from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TaskCategoryViewSet, TaskViewSet

router = DefaultRouter()
router.register(r'categories', TaskCategoryViewSet, basename='task-category')
router.register(r'tasks', TaskViewSet, basename='task')

urlpatterns = [
    path('', include(router.urls)),
]
