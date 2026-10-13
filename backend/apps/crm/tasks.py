import logging
from celery import shared_task
from apps.tenancy.models import Store
from .services import recalculate_all_store_customers

logger = logging.getLogger(__name__)


@shared_task(name='crm.recalculate_customer_rfm_scores')
def recalculate_customer_rfm_scores():
    """Daily cron to recalculate RFM scores and customer segmentation for all stores"""
    stores = Store.objects.filter(is_active=True)
    total_customers = 0

    for store in stores:
        try:
            count = recalculate_all_store_customers(store)
            total_customers += count
        except Exception as e:
            logger.error(f"Error recalculating RFM for store {store.name} ({store.id}): {e}")

    return f"Recalculated RFM metrics for {total_customers} customers across {stores.count()} stores"
