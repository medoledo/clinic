from django.contrib import admin
from .models import Patient, Visit, VisitFile


class VisitFileInline(admin.TabularInline):
    model = VisitFile
    extra = 0
    fields = ('title', 'file_type', 'file', 'uploaded_at')
    readonly_fields = ('uploaded_at',)
    # Avoid loading full file dropdown on millions of records
    show_change_link = True
    max_num = 10


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('name', 'doctor', 'phone', 'gender', 'age', 'created_at')
    list_filter = ('gender', 'created_at')
    search_fields = ('name', 'phone', 'doctor__username')
    readonly_fields = ('created_at',)
    list_select_related = ('doctor',)
    show_full_result_count = False
    list_per_page = 25
    # Use raw ID field for doctor to avoid loading all users in a dropdown
    raw_id_fields = ('doctor',)
    fieldsets = (
        ('Personal Info', {
            'fields': ('doctor', 'name', 'phone', 'date_of_birth', 'gender')
        }),
        ('Additional Info', {
            'fields': ('notes',)
        }),
        ('System', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


class VisitInline(admin.TabularInline):
    model = Visit
    extra = 0
    fields = ('visit_date', 'chief_complaint', 'diagnosis', 'doctor')
    readonly_fields = ('visit_date',)
    can_delete = False
    max_num = 5
    show_change_link = True
    raw_id_fields = ('doctor',)


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = ('visit_date', 'patient', 'doctor', 'diagnosis_summary', 'has_files')
    # Removed 'patient__doctor' from list_filter — it causes a full JOIN scan without index support
    list_filter = ('visit_date', 'doctor')
    search_fields = ('patient__name', 'doctor__username', 'chief_complaint', 'diagnosis')
    readonly_fields = ('created_at',)
    inlines = (VisitFileInline,)
    list_select_related = ('patient', 'doctor')
    show_full_result_count = False
    list_per_page = 25
    raw_id_fields = ('patient', 'doctor')
    fieldsets = (
        ('Visit Info', {
            'fields': ('patient', 'doctor', 'visit_date')
        }),
        ('Medical Details', {
            'fields': ('chief_complaint', 'symptoms', 'diagnosis', 'treatment', 'next_checkup_date')
        }),
        ('Vitals', {
            'fields': ('temperature', 'blood_pressure', 'pulse', 'weight'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('doctor_notes',),
            'classes': ('collapse',)
        }),
        ('System', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(VisitFile)
class VisitFileAdmin(admin.ModelAdmin):
    list_display = ('title', 'visit', 'doctor', 'file_type', 'uploaded_at')
    list_filter = ('file_type', 'uploaded_at')
    search_fields = ('title', 'visit__patient__name', 'doctor__username')
    readonly_fields = ('uploaded_at',)
    list_select_related = ('visit', 'doctor')
    show_full_result_count = False
    list_per_page = 25
    raw_id_fields = ('visit', 'doctor')
