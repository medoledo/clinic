from django.apps import AppConfig


class PatientsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'patients'

    def ready(self):
        """Enable SQLite WAL journal mode on startup for better concurrent read performance."""
        try:
            from django.db import connection
            # Only applies to SQLite; harmless no-op on other engines
            if 'sqlite' in connection.vendor:
                with connection.cursor() as cursor:
                    cursor.execute('PRAGMA journal_mode=WAL;')
        except Exception:
            # Startup hooks must never crash the server
            pass
