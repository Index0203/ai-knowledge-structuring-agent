from celery import Celery

from app.core.config import settings
from app.workers.retry_policy import transient_exceptions

celery_app = Celery("knowledge_agent", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_default_queue = "knowledge-agent"
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]

# Reliable delivery: a task is acknowledged after it finishes, and a lost worker
# puts its task back on the queue instead of dropping it silently.
celery_app.conf.task_acks_late = True
celery_app.conf.task_reject_on_worker_lost = True
celery_app.conf.worker_prefetch_multiplier = 1
celery_app.conf.task_default_retry_delay = settings.task_retry_backoff_seconds
celery_app.conf.task_annotations = {
    "*": {
        "autoretry_for": transient_exceptions(),
        "retry_backoff": True,
        "retry_backoff_max": settings.task_retry_backoff_max_seconds,
        "retry_jitter": True,
        "max_retries": settings.task_max_retries,
    }
}
# The reaper is the safety net for jobs whose worker disappeared mid-flight.
celery_app.conf.beat_schedule = {
    "reap-stale-jobs": {
        "task": "maintenance.reap_stale_jobs",
        "schedule": float(settings.reaper_interval_seconds),
    }
}
# Keep the beat database out of the bind-mounted source tree.
celery_app.conf.beat_schedule_filename = "/tmp/celerybeat-schedule"
celery_app.autodiscover_tasks(["app.workers"])
