import os

from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "paperless.settings")

app = Celery("paperless")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


# RKC: Schedule batched mail action processing to avoid connection storms (v1.0.17)
# Processes pending mail post-actions every 5 minutes with pooled IMAP connections
# per account, eliminating OAuth2 authentication storms that trigger Microsoft rate limiting
@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    from celery.schedules import crontab
    
    sender.add_periodic_task(
        crontab(minute='*/5'),  # Every 5 minutes
        sender.tasks['paperless_mail.mail.process_pending_mail_actions'],
        name='process-pending-mail-actions'
    )
# /end RKC edit
