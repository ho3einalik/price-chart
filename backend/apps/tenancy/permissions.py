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


ROLE_DEFAULT_PERMISSIONS = {
    Role.OWNER: ['*'],
    Role.ADMIN: ['*'],
    Role.BUSINESS_MANAGER: [
        'team.view', 'team.invite', 'team.manage_roles', 'team.remove',
        'tasks.view_all', 'tasks.create', 'tasks.assign', 'tasks.edit', 'tasks.complete', 'tasks.verify',
        'content.view', 'content.create', 'content.edit', 'content.submit', 'content.approve', 'content.reject',
        'analytics.view', 'analytics.export', 'settings.manage'
    ],
    Role.SOCIAL_MEDIA_MANAGER: [
        'tasks.view_all', 'tasks.create', 'tasks.assign', 'tasks.edit', 'tasks.complete',
        'content.view', 'content.create', 'content.edit', 'content.submit', 'content.approve', 'content.reject', 'content.publish',
        'analytics.view', 'analytics.export', 'integrations.manage'
    ],
    Role.CONTENT_CREATOR: [
        'tasks.view_assigned', 'tasks.complete',
        'content.view', 'content.create', 'content.edit', 'content.submit'
    ],
    Role.OPS_MANAGER: [
        'tasks.view_all', 'tasks.create', 'tasks.assign', 'tasks.edit', 'tasks.complete', 'tasks.verify',
        'analytics.view'
    ],
    Role.FULFILLMENT_STAFF: [
        'tasks.view_assigned', 'tasks.complete'
    ],
    Role.SUPPORT: [
        'tasks.view_assigned', 'tasks.complete'
    ],
    Role.READ_ONLY: [
        'team.view', 'tasks.view_all', 'content.view', 'analytics.view'
    ],
    Role.CUSTOM: []
}

def user_has_store_permission(membership, perm_code):
    if not membership or not membership.is_active or getattr(membership, 'status', 'ACTIVE') != 'ACTIVE':
        return False
    if membership.role in [Role.OWNER, Role.ADMIN]:
        return True
    defaults = ROLE_DEFAULT_PERMISSIONS.get(membership.role, [])
    if '*' in defaults or perm_code in defaults:
        return True
    return perm_code in (getattr(membership, 'custom_permissions', None) or [])

class IsStoreMemberPermission(permissions.BasePermission):
    """Requires request to have an active store context and valid membership"""
    message = "دسترسی به این فروشگاه مجاز نیست یا فروشگاه انتخاب نشده است."

    def has_permission(self, request, view):
        store = get_request_store(request)
        return bool(request.user and request.user.is_authenticated and store)

class IsStoreAdminOrOwnerPermission(permissions.BasePermission):
    """Requires user to be OWNER, ADMIN, or BUSINESS_MANAGER of the active store"""
    message = "این عملیات نیازمند سطح دسترسی مدیر یا مالک فروشگاه است."

    def has_permission(self, request, view):
        store = get_request_store(request)
        if not (request.user and request.user.is_authenticated and store):
            return False
        membership = getattr(request, 'membership', None)
        return bool(membership and membership.role in [Role.OWNER, Role.ADMIN, Role.BUSINESS_MANAGER])

class HasStorePermission(permissions.BasePermission):
    """Verifies that the user's role or custom permissions include the required permission"""
    def __init__(self, required_permission=None):
        self.required_permission = required_permission

    def has_permission(self, request, view):
        store = get_request_store(request)
        if not (request.user and request.user.is_authenticated and store):
            return False
        perm = getattr(view, 'required_permission', self.required_permission)
        if not perm:
            return True
        membership = getattr(request, 'membership', None)
        return user_has_store_permission(membership, perm)

class TenantFilterBackend(filters.BaseFilterBackend):
    """Restricts queryset strictly to the store bound to the current request"""
    def filter_queryset(self, request, queryset, view):
        store = get_request_store(request)
        if store and hasattr(queryset.model, 'store'):
            return queryset.filter(store=store)
        return queryset.none()


