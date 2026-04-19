from django.apps import AppConfig
from django.db.backends.signals import connection_created

def enable_sqlite_wal(sender, connection, **kwargs):
    """Enable SQLite WAL journal mode on startup for better concurrent read performance."""
    try:
        if 'sqlite' in connection.vendor:
            with connection.cursor() as cursor:
                cursor.execute('PRAGMA journal_mode=WAL;')
    except Exception:
        pass

class PatientsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'patients'

    def ready(self):
        connection_created.connect(enable_sqlite_wal)
