from django.core.management.base import BaseCommand
from patients.models import MedicalDictionary
import os

class Command(BaseCommand):
    help = 'Import Egyptian drug names from egyptian_drugs.txt into MedicalDictionary'

    def handle(self, *args, **kwargs):
        drug_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
            'egyptian_drugs.txt'
        )

        if not os.path.exists(drug_file):
            self.stdout.write(self.style.ERROR(f'File not found: {drug_file}'))
            return

        with open(drug_file, 'r', encoding='utf-8') as f:
            words = [line.strip() for line in f if line.strip()]

        created = 0
        skipped = 0
        for word in words:
            obj, was_created = MedicalDictionary.objects.get_or_create(
                word=word,
                defaults={'category': 'drug'}
            )
            if was_created:
                created += 1
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f'Done. Created: {created}, Already existed: {skipped}, Total: {MedicalDictionary.objects.count()}'
        ))