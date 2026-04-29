from django.core.management.base import BaseCommand
from django.core.cache import cache


class Command(BaseCommand):
    help = 'Clear all application caches (use if dashboard/search shows stale data).'

    def handle(self, *args, **options):
        cache.clear()
        self.stdout.write(self.style.SUCCESS('All caches cleared successfully.'))
        self.stdout.write('Reload the browser page (Ctrl+F5) if it still looks stale.')
