from rest_framework import permissions, filters
from .models import Role, StoreMembership

def get_request_store(request):
    """Dynamically resolves and caches request.store and request.membership for DRF/Django requests"""
    if getattr(request, 'store', None):
        return request.store

    if not (getattr(request, 'user', None) and request.user.is_authenticated):
        return None

    store = None
    membership = None
    store_id = (
        request.headers.get('x-store-id')
        or request.META.get('HTTP_X_STORE_ID')
        or request.GET.get('store_id')
    )
    if store_id:
        membership = StoreMembership.objects.select_related('store').filter(
            user=request.user,
            store_id=store_id,
            is_active=True
        ).first()
        if membership:
            store = membership.store
    else:
        membership = StoreMembership.objects.select_related('store').filter(
            user=request.user,
            is_active=True
        ).first()
        if membership:
            store = membership.store

    request.store = store
    request.membership = membership
    return store


class IsStoreMemberPermission(permissions.BasePermission):
    """Requires request to have an active store context and valid membership"""
    message = "دسترسی به این فروشگاه مجاز نیست یا فروشگاه انتخاب نشده است."

    def has_permission(self, request, view):
        store = get_request_store(request)
        return bool(request.user and request.user.is_authenticated and store)

class IsStoreAdminOrOwnerPermission(permissions.BasePermission):
    """Requires user to be OWNER or ADMIN of the active store"""
    message = "این عملیات نیازمند سطح دسترسی مدیر یا مالک فروشگاه است."

    def has_permission(self, request, view):
        store = get_request_store(request)
        if not (request.user and request.user.is_authenticated and store):
            return False
        membership = getattr(request, 'membership', None)
        return bool(membership and membership.role in [Role.OWNER, Role.ADMIN])

class TenantFilterBackend(filters.BaseFilterBackend):
    """Restricts queryset strictly to the store bound to the current request"""
    def filter_queryset(self, request, queryset, view):
        store = get_request_store(request)
        if store and hasattr(queryset.model, 'store'):
            return queryset.filter(store=store)
        return queryset.none()

