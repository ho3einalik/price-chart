from .models import AuditLog

def record_audit_event(store, user, action, target_type, target_id, changes=None, ip_address=None):
    return AuditLog.objects.create(
        store=store,
        user=user if user and user.is_authenticated else None,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        changes=changes or {},
        ip_address=ip_address
    )
