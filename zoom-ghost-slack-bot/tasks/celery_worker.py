import os
import ssl
from celery import Celery
from dotenv import load_dotenv

# Load .env
load_dotenv()

APP_ENV = os.getenv("APP_ENV", "development")
REDIS_URL = os.getenv("REDIS_URL")

# 🔐 SSL settings only when the URL is rediss://
ssl_options = None
if REDIS_URL.startswith("rediss://"):
    ssl_options = {"ssl_cert_reqs": ssl.CERT_NONE}

# 👇 Celery configuration with dynamic SSL
celery_app = Celery(
    "zoomghost_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
    broker_use_ssl=ssl_options,
    redis_backend_use_ssl=ssl_options
)

# 🛠 Shared settings
celery_app.conf.update(
    task_track_started=True,
    result_extended=True,
    include=[
        'tasks.zoom_tasks',
        'tasks.slack_tasks',
        'tasks.recording_tasks'
    ]
)


# ⏰ Periodic tasks hook (empty for now)
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    pass
