from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import UserProfile


class Command(BaseCommand):
    help = 'Sets up MediTrack initial data: creates admin user and UserProfile.'

    def handle(self, *args, **options):
        username = 'admin'
        password = 'admin123'

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(
                f'Admin user "{username}" already exists. Skipping creation.'
            ))
        else:
            user = User.objects.create_superuser(
                username=username,
                password=password,
                email='admin@meditrack.local',
            )
            UserProfile.objects.create(user=user, role='admin')
            self.stdout.write(self.style.SUCCESS(
                f'\n✅ MediTrack setup complete!\n'
                f'   Login at: http://127.0.0.1:8000/login/\n'
                f'   Username: {username}\n'
                f'   Password: {password}\n'
                f'   Django Admin: http://127.0.0.1:8000/admin/\n'
            ))
