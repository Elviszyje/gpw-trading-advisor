from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    
    def ready(self):
        # Import Celery tasks to ensure they are registered
        import apps.core.tasks
