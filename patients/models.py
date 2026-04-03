from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Patient(models.Model):
    GENDER_CHOICES = [('male', 'Male'), ('female', 'Female')]
    BLOOD_TYPE_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
        ('O+', 'O+'), ('O-', 'O-'),
    ]

    doctor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='patients')
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default='male')
    blood_type = models.CharField(max_length=5, choices=BLOOD_TYPE_CHOICES, blank=True)
    address = models.TextField(blank=True)
    emergency_contact_name = models.CharField(max_length=200, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            # Covers the common "fetch all patients for a doctor" query
            models.Index(fields=['doctor', 'is_active'], name='patient_doctor_active_idx'),
            # Covers ordering + pagination
            models.Index(fields=['doctor', '-created_at'], name='patient_doctor_created_idx'),
            # Covers name search
            models.Index(fields=['name'], name='patient_name_idx'),
        ]

    def __str__(self):
        return self.name

    @property
    def age(self):
        """Returns the patient's age in years, or None if DOB is not set."""
        if self.date_of_birth:
            today = timezone.now().date()
            born = self.date_of_birth
            return (
                today.year - born.year
                - ((today.month, today.day) < (born.month, born.day))
            )
        return None

    @property
    def last_visit(self):
        """
        Returns the most recent Visit object for this patient.
        NOTE: This property hits the DB on every call. Avoid using it inside
        loops — use prefetch_related('visits') on the queryset instead.
        """
        return self.visits.order_by('-visit_date').first()

    @property
    def total_visits(self):
        """
        Returns the total number of visits.
        NOTE: Avoid calling in loops — use annotate(vc=Count('visits')) instead.
        """
        return self.visits.count()


class Visit(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='visits')
    doctor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='visits')
    visit_date = models.DateTimeField(default=timezone.now)
    chief_complaint = models.TextField()
    symptoms = models.TextField(blank=True, null=True)
    diagnosis = models.TextField(blank=True, null=True)
    treatment = models.TextField(blank=True, null=True)
    temperature = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    blood_pressure = models.CharField(max_length=20, blank=True)
    pulse = models.PositiveIntegerField(null=True, blank=True)
    weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    next_checkup_date = models.DateField(null=True, blank=True)
    doctor_notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-visit_date']
        indexes = [
            # Covers "all visits for a doctor, ordered by date"
            models.Index(fields=['doctor', '-visit_date'], name='visit_doctor_date_idx'),
            # Covers "all visits for a patient, ordered by date"
            models.Index(fields=['patient', '-visit_date'], name='visit_patient_date_idx'),
            # Covers date-range analytics queries
            models.Index(fields=['visit_date'], name='visit_date_idx'),
        ]

    def __str__(self):
        return f"{self.patient.name} \u2014 {self.visit_date.strftime('%Y-%m-%d')}"

    @property
    def has_files(self):
        return self.files.exists()

    @property
    def diagnosis_summary(self):
        if self.diagnosis:
            return self.diagnosis[:80] + ('...' if len(self.diagnosis) > 80 else '')
        return ''


class VisitFile(models.Model):
    FILE_TYPE_CHOICES = [
        ('lab_result', 'Lab Result'),
        ('xray', 'X-Ray'),
        ('prescription', 'Prescription'),
        ('scan', 'Scan'),
        ('other', 'Other'),
    ]

    visit = models.ForeignKey(Visit, on_delete=models.CASCADE, related_name='files')
    doctor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='visit_files')
    title = models.CharField(max_length=200)
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES, default='other')
    file = models.FileField(upload_to='visit_files/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['visit'], name='visitfile_visit_idx'),
            models.Index(fields=['doctor'], name='visitfile_doctor_idx'),
        ]

    def __str__(self):
        return f"{self.title} \u2014 {self.visit}"

    @property
    def is_image(self):
        name = self.file.name.lower()
        return name.endswith(('.jpg', '.jpeg', '.png'))

    @property
    def is_pdf(self):
        return self.file.name.lower().endswith('.pdf')

    @property
    def file_size_display(self):
        try:
            size = self.file.size
            if size < 1024:
                return f"{size} B"
            elif size < 1024 * 1024:
                return f"{size / 1024:.1f} KB"
            else:
                return f"{size / (1024 * 1024):.1f} MB"
        except Exception:
            return "Unknown size"
