from django.utils import timezone
from .models import AutomationRule, AutomationExecutionLog, ExecutionStatus
from apps.tasks.models import Task, TaskPriority, TaskStatus
from apps.features.adapters import get_integration_adapter

def evaluate_conditions(conditions, payload):
    """Evaluate whether the event payload meets the rule conditions"""
    if not conditions:
        return True

    for key, expected_val in conditions.items():
        actual_val = payload.get(key)
        if actual_val is None:
            return False

        if key.startswith('min_'):
            try:
                if float(actual_val) < float(expected_val):
                    return False
            except (ValueError, TypeError):
                return False
        elif key.startswith('max_'):
            try:
                if float(actual_val) > float(expected_val):
                    return False
            except (ValueError, TypeError):
                return False
        elif str(actual_val).upper() != str(expected_val).upper():
            return False

    return True

def execute_actions(rule, actions, payload):
    """Execute defined actions for a triggered rule"""
    results = []
    store = rule.store

    for act in actions:
        act_type = act.get('type')

        if act_type == 'CREATE_TASK':
            title = act.get('title', f"وظیفه خودکار: {rule.name}")
            desc = act.get('description', f"ایجاد شده توسط اتوماسیون بر اساس رویداد {rule.trigger}.\nجزئیات: {payload}")
            priority = act.get('priority', TaskPriority.MEDIUM)
            Task.objects.create(
                store=store,
                title=title,
                description=desc,
                priority=priority,
                status=TaskStatus.TODO
            )
            results.append(f"وظیفه '{title}' با موفقیت در کارتابل تیم ثبت شد.")

        elif act_type == 'SEND_SMS':
            phone = payload.get('customer_phone') or payload.get('phone_number')
            template = act.get('template', 'سفارش شما در فروشگاه با موفقیت ثبت شد.')
            if phone:
                sms_adapter = get_integration_adapter('sms_gateway')
                sms_res = sms_adapter.send_sms(to=phone, message=template)
                results.append(f"پیامک به شماره {phone} ارسال شد (وضعیت: {sms_res.get('status')}).")
            else:
                results.append("شماره تلفنی در داده‌های رویداد برای ارسال پیامک یافت نشد.")

        elif act_type == 'NOTIFY_TEAM':
            results.append(f"اعلان سیستمی برای تیم ثبت شد: {act.get('message', 'رویداد اتوماسیون')}")

    return "\n".join(results)

def trigger_automation(store, trigger_event, payload):
    """Trigger all active rules matching the event for a store"""
    rules = AutomationRule.objects.filter(store=store, trigger=trigger_event, is_active=True)
    executed_count = 0

    for rule in rules:
        matches = evaluate_conditions(rule.conditions, payload)
        if not matches:
            AutomationExecutionLog.objects.create(
                rule=rule,
                trigger_event=trigger_event,
                event_payload=payload,
                status=ExecutionStatus.SKIPPED,
                details="شرایط قانون با داده‌های رویداد مطابقت نداشت."
            )
            continue

        try:
            details = execute_actions(rule, rule.actions, payload)
            rule.execution_count += 1
            rule.last_executed_at = timezone.now()
            rule.save(update_fields=['execution_count', 'last_executed_at'])

            AutomationExecutionLog.objects.create(
                rule=rule,
                trigger_event=trigger_event,
                event_payload=payload,
                status=ExecutionStatus.SUCCESS,
                details=details
            )
            executed_count += 1
        except Exception as e:
            AutomationExecutionLog.objects.create(
                rule=rule,
                trigger_event=trigger_event,
                event_payload=payload,
                status=ExecutionStatus.FAILED,
                details=f"خطا در اجرای اقدامات: {str(e)}"
            )

    return executed_count
