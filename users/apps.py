from django.apps import AppConfig
from django.conf import settings


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'

    def ready(self):
        from .astra_utils import setup_astra_connection
        if settings.ENABLE_ASTRA_SYNC:
            try:
                setup_astra_connection()
            except Exception as e:
                print(f"Error connecting to Astra DB: {str(e)}")
        else:
            print("Astra DB sync is disabled")
