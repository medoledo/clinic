from django.core.management.base import BaseCommand
from django.conf import settings
from patients.models import MedicalDictionary


class Command(BaseCommand):
    help = 'Import Egyptian drug names from egyptian_drugs.txt into MedicalDictionary'

    def handle(self, *args, **kwargs):
        drug_file = settings.BASE_DIR / 'egyptian_drugs.txt'

        if not drug_file.exists():
            self.stdout.write(self.style.ERROR(f'File not found: {drug_file}'))
            return

        with open(drug_file, 'r', encoding='utf-8') as f:
            words = [line.strip() for line in f if line.strip()]

        if not words:
            self.stdout.write(self.style.WARNING('No words found in file.'))
            return

        # M1: Use bulk_create with ignore_conflicts — ~100x faster than per-row get_or_create
        objs = [MedicalDictionary(word=w, category='drug') for w in words]
        MedicalDictionary.objects.bulk_create(objs, ignore_conflicts=True)

        self.stdout.write(self.style.SUCCESS(
            f'Done. Attempted: {len(objs)}, Total in DB: {MedicalDictionary.objects.count()}'
        ))
