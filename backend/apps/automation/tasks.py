import logging
from celery import shared_task
from apps.tenancy.models import Store
from .services import trigger_automation

logger = logging.getLogger(__name__)


@shared_task(name='automation.process_async_automation_event')
def process_async_automation_event(store_id, trigger_event, payload):
    """Processes an automation trigger asynchronously"""
    try:
        store = Store.objects.get(id=store_id)
        count = trigger_automation(store=store, trigger_event=trigger_event, payload=payload)
        return f"Executed {count} rules for event {trigger_event} in store {store.name}"
    except Store.DoesNotExist:
        logger.error(f"Store {store_id} not found for automation trigger {trigger_event}")
        return "Store not found"
    except Exception as e:
        logger.error(f"Error processing async automation for store {store_id}: {e}")
        raise
