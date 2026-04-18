from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import pre_delete
from django.dispatch import receiver


class Patient(models.Model):
    GENDER_CHOICES = [('male', 'Male'), ('female', 'Female')]

    doctor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='patients')
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default='male')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['doctor', '-created_at'], name='patient_doctor_created_idx'),
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
            # Covers upcoming_visits view filter — avoids full table scan
            models.Index(fields=['next_checkup_date'], name='visit_checkup_date_idx'),
            models.Index(fields=['doctor', 'next_checkup_date'], name='visit_doctor_checkup_idx'),
        ]

    def __str__(self):
        return f"{self.patient.name} \u2014 {self.visit_date.strftime('%Y-%m-%d')}"

    @property
    def has_files(self):
        # Optimization: use prefetch cache if available
        if hasattr(self, '_prefetched_objects_cache') and 'files' in self._prefetched_objects_cache:
            return any(f.file for f in self.files.all())
        return self.files.exclude(file='').exclude(file__isnull=True).exists()

    @property
    def has_links(self):
        # Optimization: use prefetch cache if available
        if hasattr(self, '_prefetched_objects_cache') and 'files' in self._prefetched_objects_cache:
            return any(f.link_url for f in self.files.all())
        return self.files.filter(link_url__isnull=False).exclude(link_url='').exists()

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
    file = models.FileField(upload_to='visit_files/', blank=True, null=True)
    link_url = models.URLField(max_length=1000, blank=True, null=True)
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
    def is_link(self):
        return bool(self.link_url)

    @property
    def is_image(self):
        if not self.file: return False
        name = self.file.name.lower()
        return name.endswith(('.jpg', '.jpeg', '.png'))

    @property
    def is_pdf(self):
        if not self.file: return False
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


class MedicalDictionary(models.Model):
    """Master dictionary of known correct medical words/drug names."""
    word = models.CharField(max_length=200, unique=True, db_index=True)
    category = models.CharField(max_length=50, default='drug', choices=[
        ('drug', 'Drug Name'),
        ('diagnosis', 'Diagnosis'),
        ('symptom', 'Symptom'),
        ('procedure', 'Procedure'),
        ('other', 'Other'),
    ])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Medical Dictionary'
        verbose_name_plural = 'Medical Dictionary'

    def __str__(self):
        return self.word


class TranscriptionCorrection(models.Model):
    """Personal learning table — maps wrong heard words to correct ones."""
    doctor = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='transcription_corrections'
    )
    wrong_word = models.CharField(max_length=200, db_index=True)
    correct_word = models.CharField(max_length=200)
    usage_count = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('doctor', 'wrong_word')
        ordering = ['-usage_count']

    def __str__(self):
        return f'{self.wrong_word} → {self.correct_word} ({self.usage_count}x)'


# ─── Signal: delete physical file when VisitFile record is removed ─────────────
@receiver(pre_delete, sender=VisitFile)
def delete_visitfile_on_delete(sender, instance, **kwargs):
    """
    Fires on direct delete AND cascade delete (e.g., when Visit or Patient is deleted).
    Removes the physical file from storage so media/ directory stays clean.
    """
    if instance.file:
        instance.file.delete(save=False)
