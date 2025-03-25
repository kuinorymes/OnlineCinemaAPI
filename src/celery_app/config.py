from celery import Celery
from celery.schedules import crontab

from config.dependencies import get_settings
from celery_app.tasks import delete_expired_tokens

settings = get_settings()


app = Celery("tasks")

app.conf.broker_url = settings.CELERY_BROKER_URL
app.conf.result_backend = settings.CELERY_BACKEND_URL

app.conf.beat_schedule = {
    "cleanup_expired_tokens": {
        "task": "celery_app.tasks.delete_expired_tokens_wrapper",
        "schedule": crontab(),
    }
}
