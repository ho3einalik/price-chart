from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied
from apps.tenancy.permissions import get_request_store
from .services import FeatureService


class RequiresFeature(permissions.BasePermission):
    """
    DRF permission class that ensures a specific feature is entitled,
    enabled, dependencies satisfied, and integration ready for the active store.
    """
    def __init__(self, feature_key: str = None, required_user_permission: str = None):
        self.feature_key = feature_key
        self.required_user_permission = required_user_permission

    def __call__(self):
        # Support both RequiresFeature('key') and RequiresFeature class factory
        return self

    def has_permission(self, request, view):
        store = get_request_store(request)
        if not store:
            return False

        feature_key = getattr(view, 'required_feature', self.feature_key)
        if not feature_key:
            return True
        user_perm = getattr(view, 'required_permission', self.required_user_permission)

        allowed, code, message = FeatureService.check_feature_access(
            store=store,
            feature_key=feature_key,
            user=request.user,
            required_permission=user_perm
        )

        if not allowed:
            raise PermissionDenied({
                'code': code,
                'feature': feature_key,
                'message': message,
                'reactivation_hint': 'می‌توانید وضعیت و تنظیمات این ماژول را در بخش تنظیمات فروشگاه بررسی کنید.'
            })

        return True
