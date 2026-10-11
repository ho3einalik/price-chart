from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    path('admin/', admin.site.urls),

    # OpenAPI Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # API v1 routes
    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/tenancy/', include('apps.tenancy.urls')),
    path('api/v1/catalog/', include('apps.catalog.urls')),
    path('api/v1/inventory/', include('apps.inventory.urls')),
    path('api/v1/orders/', include('apps.orders.urls')),
    path('api/v1/payments/', include('apps.payments.urls')),
    path('api/v1/fulfillment/', include('apps.fulfillment.urls')),
    path('api/v1/daily-actions/', include('apps.daily_actions.urls')),
    path('api/v1/analytics/', include('apps.analytics.urls')),
    path('api/v1/tasks/', include('apps.tasks.urls')),
    path('api/v1/social/', include('apps.social.urls')),
    path('api/v1/features/', include('apps.features.urls')),
]
