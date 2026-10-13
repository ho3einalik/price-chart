import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('shoppilot')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'marketing-check-abandoned-carts': {
        'task': 'marketing.check_abandoned_carts_and_notify',
        'schedule': 1800.0,  # Every 30 minutes
    },
    'crm-recalculate-customer-rfm': {
        'task': 'crm.recalculate_customer_rfm_scores',
        'schedule': 86400.0,  # Every 24 hours (daily)
    },
    'inventory-check-low-stock': {
        'task': 'inventory.check_low_stock_and_alert',
        'schedule': 3600.0,  # Every 1 hour
    },
}

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

