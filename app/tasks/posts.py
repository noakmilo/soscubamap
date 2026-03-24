from app.celery_app import celery
from app.services.post_expiration import expire_old_map_alert_posts


@celery.task(
    name="app.tasks.posts.expire_map_alert_posts",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 2},
)
def expire_map_alert_posts(self):
    return expire_old_map_alert_posts()
