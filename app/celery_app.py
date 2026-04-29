"""
Celery application configuration.
Uses Redis as broker and result backend with separate queues for each module.
"""

from celery import Celery
from kombu import Queue
import os

# Load env for standalone worker process
from dotenv import load_dotenv
load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Create Celery app
celery_app = Celery(
    "leadgenai",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "app.tasks.email_tasks",
        "app.tasks.whatsapp_tasks",
        "app.tasks.call_tasks",
        "app.tasks.analytics_tasks",
    ],
)

# Celery configuration
celery_app.conf.update(
    # --- Serialization ---
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # --- Task Execution ---
    task_track_started=True,
    task_acks_late=True,           # Acknowledge after completion (reliability)
    worker_prefetch_multiplier=1,  # Fair task distribution

    # --- Result Backend ---
    result_expires=3600,           # Results expire after 1 hour

    # --- Retry Defaults ---
    task_default_retry_delay=60,   # 60 seconds before retry
    task_max_retries=3,

    # --- Rate Limiting ---
    task_default_rate_limit="10/m",

    # --- Queues ---
    task_queues=(
        Queue("default", routing_key="default"),
        Queue("email", routing_key="email.#"),
        Queue("whatsapp", routing_key="whatsapp.#"),
        Queue("calls", routing_key="calls.#"),
        Queue("analytics", routing_key="analytics.#"),
    ),
    task_default_queue="default",

    # --- Task Routes ---
    task_routes={
        "app.tasks.email_tasks.*": {"queue": "email"},
        "app.tasks.whatsapp_tasks.*": {"queue": "whatsapp"},
        "app.tasks.call_tasks.*": {"queue": "calls"},
        "app.tasks.analytics_tasks.*": {"queue": "analytics"},
    },

    # --- Worker ---
    worker_concurrency=4,
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks (memory leak prevention)
)
