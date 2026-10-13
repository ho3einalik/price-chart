import logging
from typing import Dict, Any, Tuple, Optional, List
from rest_framework.exceptions import ValidationError, PermissionDenied

from .models import StoreFeatureSetting, SubscriptionTier, IntegrationState
from .registry import (
    FEATURE_CATALOG,
    FeatureDefinition,
    get_feature,
    is_tier_sufficient,
    get_dependent_features
)
from .adapters import IntegrationRegistry
from apps.audit.services import record_audit_event

logger = logging.getLogger(__name__)


class FeatureService:
    @staticmethod
    def get_or_create_settings(store) -> StoreFeatureSetting:
        settings, created = StoreFeatureSetting.objects.get_or_create(
            store=store,
            defaults={
                'tier': SubscriptionTier.PRO,
                'enabled_features': [],
                'disabled_features': []
            }
        )
        return settings

    @classmethod
    def is_feature_entitled(cls, store, feature_key: str) -> Tuple[bool, str]:
        """
        Verifies if the store's current subscription tier entitles it to this feature.
        """
        feat = get_feature(feature_key)
        if not feat:
            return False, f"ویژگی '{feature_key}' در کاتالوگ پلتفرم تعریف نشده است."

        settings = cls.get_or_create_settings(store)
        if is_tier_sufficient(settings.tier, feat.min_tier):
            return True, "مجاز بر اساس پلن اشتراک"

        return False, f"این قابلیت نیازمند اشتراک سطح {feat.min_tier} یا بالاتر است."

    @classmethod
    def get_missing_dependencies(cls, store, feature_key: str) -> List[str]:
        """
        Checks if any prerequisite features are missing or disabled.
        """
        feat = get_feature(feature_key)
        if not feat or not feat.depends_on:
            return []

        missing = []
        for dep_key in feat.depends_on:
            if not cls.is_feature_active(store, dep_key):
                missing.append(dep_key)
        return missing

    @classmethod
    def is_feature_active(cls, store, feature_key: str) -> bool:
        """
        Determines whether a feature is fully active and enabled for the given store.
        """
        feat = get_feature(feature_key)
        if not feat:
            return False

        # Core features are always active
        if feat.is_core:
            return True

        # Check subscription entitlement
        entitled, _ = cls.is_feature_entitled(store, feature_key)
        if not entitled:
            return False

        settings = cls.get_or_create_settings(store)

        # If explicitly disabled by user
        if feature_key in (settings.disabled_features or []):
            return False

        # If explicitly enabled
        if feature_key in (settings.enabled_features or []):
            # Check dependencies
            if cls.get_missing_dependencies(store, feature_key):
                return False
            return True

        # Fallback to feature's default state
        if feat.default_enabled:
            if cls.get_missing_dependencies(store, feature_key):
                return False
            return True

        return False

    @classmethod
    def check_feature_access(cls, store, feature_key: str, user=None, required_permission: Optional[str] = None) -> Tuple[bool, str, str]:
        """
        Comprehensive access verification:
        Checks Entitlement -> Store Enablement -> Dependencies -> Integrations -> User Permissions.
        Returns: (is_allowed, code, message_fa)
        """
        feat = get_feature(feature_key)
        if not feat:
            return False, "FEATURE_NOT_FOUND", f"ویژگی '{feature_key}' یافت نشد."

        # 1. Core check
        if feat.is_core:
            return True, "ACCESS_GRANTED", "قابلیت اصلی سیستم"

        # 2. Plan Entitlement
        entitled, reason = cls.is_feature_entitled(store, feature_key)
        if not entitled:
            return False, "PLAN_RESTRICTED", f"این قابلیت در پلن اشتراک فعلی شما موجود نیست. ({reason})"

        # 3. Store-level toggle and activation check
        settings = cls.get_or_create_settings(store)
        if feature_key in (settings.disabled_features or []):
            return False, "FEATURE_DISABLED", f"ماژول '{feat.name_fa}' توسط مالک فروشگاه غیرفعال شده است."

        # 4. Dependency Check
        missing_deps = cls.get_missing_dependencies(store, feature_key)
        if missing_deps:
            missing_names = [get_feature(k).name_fa if get_feature(k) else k for k in missing_deps]
            return False, "DEPENDENCY_MISSING", f"این قابلیت نیازمند فعال بودن: {', '.join(missing_names)} است."

        if not cls.is_feature_active(store, feature_key):
            return False, "FEATURE_DISABLED", f"ماژول '{feat.name_fa}' برای این فروشگاه فعال نشده است."

        # 5. Integration Readiness
        if feat.required_integrations:
            for integ_name in feat.required_integrations:
                adapter = IntegrationRegistry.get_adapter(integ_name)
                if adapter and not adapter.is_ready(store):
                    health = adapter.health_check(store)
                    return False, "INTEGRATION_NOT_READY", f"اتصال سرویس '{adapter.display_name_fa}' آماده نیست: {health.message}"

        # 6. User RBAC permission check (if user provided)
        if user and required_permission:
            from apps.tenancy.permissions import user_has_store_permission, StoreMembership
            membership = StoreMembership.objects.filter(store=store, user=user, is_active=True).first()
            if not user_has_store_permission(membership, required_permission):
                return False, "USER_UNAUTHORIZED", "شما دسترسی لازم برای استفاده از این قابلیت را ندارید."

        return True, "ACCESS_GRANTED", "دسترسی مجاز است."

    @classmethod
    def toggle_feature(cls, store, feature_key: str, enable: bool, actor=None) -> Dict[str, Any]:
        """
        Enables or disables an optional feature with safety checks.
        Never deletes existing data.
        """
        feat = get_feature(feature_key)
        if not feat:
            raise ValidationError({"feature": f"ویژگی '{feature_key}' نامعتبر است."})

        if feat.is_core:
            raise ValidationError({"feature": "ماژول‌های پایه و اصلی فروشگاه قابل غیرفعال‌سازی نیستند."})

        settings = cls.get_or_create_settings(store)
        enabled_list = list(settings.enabled_features or [])
        disabled_list = list(settings.disabled_features or [])

        if enable:
            # Check plan entitlement before enabling
            entitled, reason = cls.is_feature_entitled(store, feature_key)
            if not entitled:
                raise ValidationError({"feature": reason})

            # Check dependencies
            missing = cls.get_missing_dependencies(store, feature_key)
            if missing:
                missing_names = [get_feature(k).name_fa if get_feature(k) else k for k in missing]
                raise ValidationError({
                    "feature": f"ابتدا باید پیش‌نیازهای این ماژول را فعال کنید: {', '.join(missing_names)}"
                })

            if feature_key in disabled_list:
                disabled_list.remove(feature_key)
            if feature_key not in enabled_list:
                enabled_list.append(feature_key)

            action_type = "FEATURE_ENABLED"
            note = f"ماژول '{feat.name_fa}' فعال شد."
        else:
            # Disabling feature: warn about dependents
            dependents = get_dependent_features(feature_key)
            active_dependents = [d.name_fa for d in dependents if cls.is_feature_active(store, d.key)]

            if feature_key in enabled_list:
                enabled_list.remove(feature_key)
            if feature_key not in disabled_list:
                disabled_list.append(feature_key)

            action_type = "FEATURE_DISABLED"
            note = f"ماژول '{feat.name_fa}' غیرفعال شد. سوابق و اطلاعات ذخیره‌شده دست‌نخورده باقی می‌مانند."

        settings.enabled_features = enabled_list
        settings.disabled_features = disabled_list
        settings.save()

        if actor:
            record_audit_event(
                store=store,
                user=actor,
                action=action_type,
                target_type="FeatureSetting",
                target_id=feature_key,
                changes={'feature': feature_key, 'enabled': enable}
            )

        return {
            'feature': feature_key,
            'is_active': enable,
            'message': note,
            'dependents_impacted': active_dependents if not enable else []
        }

    @classmethod
    def get_store_feature_catalog(cls, store) -> List[Dict[str, Any]]:
        """
        Returns full list of features annotated with current store activation status,
        entitlements, missing dependencies, and impact notes.
        """
        settings = cls.get_or_create_settings(store)
        statuses = []

        for feat in FEATURE_CATALOG.values():
            entitled, ent_reason = cls.is_feature_entitled(store, feat.key)
            is_active = cls.is_feature_active(store, feat.key)
            missing_deps = cls.get_missing_dependencies(store, feat.key)
            dependents = [d.key for d in get_dependent_features(feat.key)]

            # Check integration status if required
            integration_info = []
            for integ in feat.required_integrations:
                adapter = IntegrationRegistry.get_adapter(integ)
                if adapter:
                    health = adapter.health_check(store)
                    integration_info.append({
                        'name': integ,
                        'display_name': adapter.display_name_fa,
                        'state': health.state,
                        'is_ready': health.state == IntegrationState.CONNECTED
                    })

            statuses.append({
                'key': feat.key,
                'name_fa': feat.name_fa,
                'description_fa': feat.description_fa,
                'category': feat.category,
                'is_core': feat.is_core,
                'is_entitled': entitled,
                'is_active': is_active,
                'min_tier': feat.min_tier,
                'depends_on': feat.depends_on,
                'missing_dependencies': missing_deps,
                'dependents': dependents,
                'integrations': integration_info,
                'impact_warning_fa': feat.impact_warning_fa
            })

        return statuses
