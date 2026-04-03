from django.contrib import admin
from .models import Patient, Visit, VisitFile


class VisitFileInline(admin.TabularInline):
    model = VisitFile
    extra = 0
    fields = ('title', 'file_type', 'file', 'uploaded_at')
    readonly_fields = ('uploaded_at',)


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('name', 'doctor', 'phone', 'gender', 'age', 'is_active', 'created_at')
    list_filter = ('gender', 'blood_type', 'is_active', 'doctor', 'created_at')
    search_fields = ('name', 'phone', 'doctor__username')
    readonly_fields = ('created_at',)
    fieldsets = (
        ('Personal Info', {
            'fields': ('doctor', 'name', 'phone', 'date_of_birth', 'gender', 'blood_type')
        }),
        ('Additional Info', {
            'fields': ('address', 'emergency_contact_name', 'emergency_contact_phone', 'notes', 'is_active')
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


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = ('visit_date', 'patient', 'doctor', 'diagnosis_summary', 'has_files')
    list_filter = ('visit_date', 'doctor', 'patient__doctor')
    search_fields = ('patient__name', 'doctor__username', 'chief_complaint', 'diagnosis')
    readonly_fields = ('created_at',)
    inlines = (VisitFileInline,)
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
    list_filter = ('file_type', 'uploaded_at', 'doctor')
    search_fields = ('title', 'visit__patient__name', 'doctor__username')
    readonly_fields = ('uploaded_at',)
