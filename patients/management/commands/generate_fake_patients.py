import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from patients.models import Patient, Visit

class Command(BaseCommand):
    help = 'Generate 10,000 fake patients with visits for doctor Basyony12'

    def handle(self, *args, **kwargs):
        username = 'Basyony12'
        try:
            doctor = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User {username} not found'))
            return

        # Check if patients already generated to avoid duplicates if rerun
        existing_test_patients = Patient.objects.filter(doctor=doctor, notes="Generated for performance testing")
        if existing_test_patients.exists():
            self.stdout.write(self.style.WARNING(f'Found existing test patients. Proceeding to add visits if missing...'))
            new_patient_ids = existing_test_patients.values_list('id', flat=True)
        else:
            self.stdout.write(f'Generating 10,000 patients for {username}...')

            first_names_ar = ["أحمد", "محمد", "علي", "محمود", "ليلى", "سارة", "فاطمة", "مريم", "ياسين", "عمر", "إبراهيم", "يوسف", "فريد", "حمزة", "ياسر"]
            last_names_ar = ["محمود", "علي", "سليمان", "المنصوري", "بدر", "شلبي", "مصطفى", "رزق", "حامد", "شاكر", "إسماعيل", "خالد"]
            
            first_names_en = ["Adam", "Noor", "Hassan", "Kareem", "Maya", "Lina", "Omar", "Zain", "Sami", "Farah", "Youssef", "Sarah"]
            last_names_en = ["Nasser", "Abbas", "Khoury", "Said", "Haddad", "Taha", "Hariri", "Zaid", "Mansour", "Haroun"]

            patients_to_create = []
            for i in range(10000):
                if random.random() > 0.4:
                    full_name = f"{random.choice(first_names_ar)} {random.choice(last_names_ar)}"
                else:
                    full_name = f"{random.choice(first_names_en)} {random.choice(last_names_en)}"
                
                phone = f"01{''.join([str(random.randint(0, 9)) for _ in range(9)])}"
                gender = random.choice(['male', 'female'])
                dob = date(1950, 1, 1) + timedelta(days=random.randint(0, 25000))
                
                patients_to_create.append(Patient(
                    doctor=doctor,
                    name=full_name,
                    phone=phone,
                    gender=gender,
                    date_of_birth=dob,
                    notes="Generated for performance testing"
                ))

            with transaction.atomic():
                Patient.objects.bulk_create(patients_to_create)
            
            self.stdout.write(self.style.SUCCESS(f'Successfully created 10,000 patients.'))
            new_patient_ids = Patient.objects.filter(doctor=doctor, notes="Generated for performance testing").values_list('id', flat=True)

        self.stdout.write('Generating visits for patients...')
        
        symptoms_list = ["كحه مستمرة", "صداع", "ألم في الظهر", "حمى خفيفة", "ضيق في التنفس", "ألم في المعدة", "إرهاق"]
        diagnosis_list = ["نزلة برد", "التهاب شعبي", "شد عضلي", "نزلة معوية", "ضغط دم مرتفع", "فحص دوري"]
        treatment_list = ["راحة وفيتامين سي", "مضاد حيوي 500mg", "مسكن آلام عند اللزوم", "تنظيم نظام غذائي", "متابعة بعد أسبوع"]

        visits_to_create = []
        for p_id in new_patient_ids:
            # Check if patient already has visits (avoid doubling if rerun)
            if Visit.objects.filter(patient_id=p_id).exists():
                continue

            num_visits = random.randint(1, 2)
            for _ in range(num_visits):
                visit_date = timezone.now() - timedelta(days=random.randint(0, 365))
                visits_to_create.append(Visit(
                    patient_id=p_id,
                    doctor=doctor,
                    visit_date=visit_date,
                    chief_complaint=random.choice(symptoms_list),
                    symptoms=random.choice(symptoms_list),
                    diagnosis=random.choice(diagnosis_list),
                    treatment=random.choice(treatment_list),
                    temperature=round(random.uniform(36.5, 39.0), 1),
                    blood_pressure=f"{random.randint(110, 150)}/{random.randint(70, 95)}",
                    pulse=random.randint(60, 100),
                    weight=round(random.uniform(50, 100), 1)
                ))
        
        chunk_size = 5000
        for i in range(0, len(visits_to_create), chunk_size):
            chunk = visits_to_create[i:i + chunk_size]
            with transaction.atomic():
                Visit.objects.bulk_create(chunk)
                
        self.stdout.write(self.style.SUCCESS(f'Successfully created missing visits.'))
