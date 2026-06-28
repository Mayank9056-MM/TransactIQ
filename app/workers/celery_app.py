from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "transactiq",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"]
)

celery_app.conf.update(
    # Serialisation
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Reliability
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    # Visibility
    task_track_started=True,
    task_send_sent_event=True,
    # Timezone
    timezone="UTC",
    enable_utc=True
)