import logging
from decimal import Decimal
from django.utils import timezone
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
                'tier': SubscriptionTier.FREE,
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

    @classmethod
    def check_plan_quota(cls, store, quota_type: str, increment: int = 0) -> Tuple[bool, int, int, str]:
        """
        Validates quantitative resource limits based on store's subscription tier.
        quota_type can be: 'products', 'members', 'stores', 'monthly_orders'
        Returns: (is_allowed, current_count, max_limit, message_fa)
        """
        from .registry import get_plan_limits
        settings = cls.get_or_create_settings(store)
        limits = get_plan_limits(settings.tier)

        if quota_type == 'products':
            from apps.catalog.models import Product
            current = Product.objects.filter(store=store).count()
            limit = limits.get('max_products', 50)
            allowed = (current + increment) <= limit if increment > 0 else (current < limit)
            msg = f"سقف تعداد محصولات در پلن {settings.get_tier_display()} ({limit} محصول) تکمیل شده است. لطفاً پلن خود را ارتقا دهید." if not allowed else ""
            return allowed, current, limit, msg

        elif quota_type == 'members':
            from apps.tenancy.models import StoreMembership, MembershipStatus
            current = StoreMembership.objects.filter(store=store, is_active=True, status=MembershipStatus.ACTIVE).count()
            limit = limits.get('max_members', 2)
            allowed = (current + increment) <= limit if increment > 0 else (current < limit)
            msg = f"سقف تعداد اعضای تیم در پلن {settings.get_tier_display()} ({limit} نفر) تکمیل شده است. لطفاً پلن خود را ارتقا دهید." if not allowed else ""
            return allowed, current, limit, msg

        elif quota_type == 'stores':
            from apps.tenancy.models import Store
            business = getattr(store, 'business', None)
            current = Store.objects.filter(business=business, is_active=True).count() if business else 1
            limit = limits.get('max_stores', 1)
            allowed = (current + increment) <= limit if increment > 0 else (current < limit)
            msg = f"سقف تعداد فروشگاه‌های مجاز در این کسب‌وکار بر اساس پلن فعلی ({limit} فروشگاه) تکمیل شده است." if not allowed else ""
            return allowed, current, limit, msg

        elif quota_type == 'monthly_orders':
            from apps.orders.models import Order
            start_of_month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            current = Order.objects.filter(store=store, created_at__gte=start_of_month).count()
            limit = limits.get('max_monthly_orders', 100)
            allowed = (current + increment) <= limit if increment > 0 else (current < limit)
            msg = f"سقف سفارشات ماهانه در پلن {settings.get_tier_display()} ({limit} سفارش در ماه) تکمیل شده است." if not allowed else ""
            return allowed, current, limit, msg

        return True, 0, 999999, ""

    @classmethod
    def enforce_plan_quota(cls, store, quota_type: str, increment: int = 0):
        allowed, current, limit, msg = cls.check_plan_quota(store, quota_type, increment=increment)
        if not allowed:
            raise PermissionDenied({
                'error': msg,
                'quota_type': quota_type,
                'current_count': current,
                'max_limit': limit,
                'tier': cls.get_or_create_settings(store).tier,
                'action_hint': 'برای افزایش ظرفیت و ثبت آیتم جدید، پلن اشتراک خود را ارتقا دهید.'
            })


from .models import SubscriptionInvoice, InvoiceStatus
from apps.payments.gateways import get_payment_gateway
from django.db import transaction
import uuid

SUBSCRIPTION_TIER_PRICES = {
    SubscriptionTier.FREE: Decimal('0'),
    SubscriptionTier.STARTER: Decimal('290000'),
    SubscriptionTier.PRO: Decimal('590000'),
    SubscriptionTier.ENTERPRISE: Decimal('1490000'),
}


class SubscriptionPaymentService:
    @staticmethod
    def get_tier_price(tier: str, billing_cycle: str = 'MONTHLY') -> Decimal:
        base_price = SUBSCRIPTION_TIER_PRICES.get(tier, Decimal('0'))
        if billing_cycle == 'ANNUAL':
            return base_price * Decimal('10')
        return base_price

    @classmethod
    def create_subscription_invoice(cls, store, tier: str, billing_cycle: str = 'MONTHLY') -> SubscriptionInvoice:
        amount = cls.get_tier_price(tier, billing_cycle)
        ref = f"INV-REF-{uuid.uuid4().hex[:12].upper()}"

        if amount == Decimal('0') or tier == SubscriptionTier.FREE:
            invoice = SubscriptionInvoice.objects.create(
                store=store,
                tier=tier,
                amount=amount,
                billing_cycle=billing_cycle,
                status=InvoiceStatus.PAID,
                payment_reference=ref,
                paid_at=timezone.now()
            )
            cls.apply_paid_subscription_invoice(invoice)
            return invoice

        invoice = SubscriptionInvoice.objects.create(
            store=store,
            tier=tier,
            amount=amount,
            billing_cycle=billing_cycle,
            status=InvoiceStatus.PENDING,
            payment_reference=ref
        )
        return invoice

    @classmethod
    def initiate_subscription_payment(cls, invoice: SubscriptionInvoice, store, callback_url: str, gateway_name: str = 'zarinpal') -> Dict[str, Any]:
        if invoice.store_id != store.id:
            raise ValidationError("این صورتحساب متعلق به این فروشگاه نیست.")
        if invoice.status == InvoiceStatus.PAID:
            raise ValidationError("این صورتحساب قبلاً تسویه شده است.")
        if invoice.amount <= 0:
            cls.apply_paid_subscription_invoice(invoice)
            return {'success': True, 'message': 'پلن رایگان فعال شد.'}

        gateway = get_payment_gateway(gateway_name)
        if not gateway:
            raise ValidationError(f"درگاه پرداخت '{gateway_name}' در سامانه موجود نیست.")

        desc = f"اشتراک {invoice.get_tier_display()} برای فروشگاه {store.name} (شناسه: {invoice.payment_reference})"

        res = gateway.request_payment(
            amount=invoice.amount,
            callback_url=callback_url,
            description=desc,
            order_id=str(invoice.id),
            store=store,
            currency='IRT'
        )

        if not res.get('success'):
            return res

        authority = res.get('authority', '')
        with transaction.atomic():
            inv = SubscriptionInvoice.objects.select_for_update().get(id=invoice.id)
            inv.authority = authority
            inv.gateway = gateway_name
            inv.payment_attempt_at = timezone.now()
            inv.save(update_fields=['authority', 'gateway', 'payment_attempt_at'])

        return res

    @classmethod
    def verify_subscription_payment(cls, authority: str, store=None, gateway_name: str = 'zarinpal') -> Tuple[bool, SubscriptionInvoice, str]:
        if not authority:
            raise ValidationError("شناسه ارجاع authority الزامی است.")

        with transaction.atomic():
            qs = SubscriptionInvoice.objects.select_for_update().filter(authority=authority)
            if store:
                qs = qs.filter(store=store)
            invoice = qs.first()

            if not invoice:
                raise ValidationError("صورتحسابی برای این شناسه ارجاع درگاه یافت نشد.")

            if invoice.status == InvoiceStatus.PAID:
                return True, invoice, "این صورتحساب قبلاً پرداخت و فعال شده است."

            gateway = get_payment_gateway(invoice.gateway or gateway_name)
            if not gateway:
                raise ValidationError("درگاه پرداخت پشتیبانی نمی‌شود.")

            verify_res = gateway.verify_payment(
                authority=authority,
                amount=invoice.amount,
                store=invoice.store,
                currency='IRT'
            )

            if verify_res.success:
                invoice.status = InvoiceStatus.PAID
                invoice.paid_at = timezone.now()
                invoice.gateway_tracking_code = verify_res.tracking_code
                invoice.metadata['gateway_verification'] = verify_res.raw_response
                invoice.save()
                cls.apply_paid_subscription_invoice(invoice)
                return True, invoice, verify_res.message
            else:
                invoice.status = InvoiceStatus.FAILED
                invoice.metadata['gateway_error'] = verify_res.raw_response
                invoice.save()
                return False, invoice, verify_res.message

    @classmethod
    def admin_manual_override_invoice(cls, invoice_id, actor, reason: str, tracking_code: str = "") -> SubscriptionInvoice:
        if not (actor and (actor.is_staff or actor.is_superuser)):
            raise PermissionDenied("تنها مدیران ارشد پلتفرم مجاز به تأیید دستی صورتحساب اشتراک هستند.")
        if not reason or len(reason.strip()) < 5:
            raise ValidationError("ذکر دلیل معتبر و مستند برای تأیید دستی صورتحساب الزامی است.")

        with transaction.atomic():
            invoice = SubscriptionInvoice.objects.select_for_update().get(id=invoice_id)
            if invoice.status == InvoiceStatus.PAID:
                return invoice

            invoice.status = InvoiceStatus.PAID
            invoice.paid_at = timezone.now()
            invoice.gateway_tracking_code = tracking_code or f"MANUAL-ADMIN-{actor.id}-{uuid.uuid4().hex[:6].upper()}"
            invoice.metadata['manual_override'] = {
                'approved_by_id': str(actor.id),
                'approved_by': getattr(actor, 'username', str(actor)),
                'reason': reason,
                'at': timezone.now().isoformat()
            }
            invoice.save()
            cls.apply_paid_subscription_invoice(invoice)

            record_audit_event(
                store=invoice.store,
                user=actor,
                action="SUBSCRIPTION_MANUAL_OVERRIDE",
                target_type="SubscriptionInvoice",
                target_id=str(invoice.id),
                changes={'tier': invoice.tier, 'reason': reason, 'amount': str(invoice.amount)}
            )
            return invoice

    @classmethod
    def apply_paid_subscription_invoice(cls, invoice: SubscriptionInvoice):
        """Authoritatively upgrades the store's feature settings to the invoice's tier"""
        settings = FeatureService.get_or_create_settings(invoice.store)
        old_tier = settings.tier
        settings.tier = invoice.tier
        settings.save(update_fields=['tier', 'updated_at'])

        record_audit_event(
            store=invoice.store,
            user=None,
            action="SUBSCRIPTION_TIER_UPGRADED",
            target_type="StoreFeatureSetting",
            target_id=str(settings.id),
            changes={'old_tier': old_tier, 'new_tier': settings.tier, 'invoice_id': str(invoice.id)}
        )
        return settings

