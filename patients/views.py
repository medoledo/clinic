import os
import re
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.core.paginator import Paginator
from django.db.models import Count, Max, Q
from django.views.decorators.http import require_GET, require_POST
from django.core.cache import cache
from django.contrib.auth.decorators import login_required

from accounts.decorators import doctor_required
from .models import Patient, Visit, VisitFile, MedicalDictionary, TranscriptionCorrection
from .utils import apply_personal_corrections, find_suggestions, regex_parse_transcript


# ─────────────────────────── Constants ────────────────────────────────────────

ALLOWED_EXTENSIONS = frozenset(['.jpg', '.jpeg', '.png', '.pdf'])
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


# ─────────────────────────── Dashboard ────────────────────────────────────────

@doctor_required
def dashboard(request):
    today = timezone.now().date()
    first_of_month = today.replace(day=1)
    doctor = request.user

    total_patients = Patient.objects.filter(doctor=doctor).count()
    today_visits = Visit.objects.filter(doctor=doctor, visit_date__date=today).count()
    month_visits = Visit.objects.filter(
        doctor=doctor,
        visit_date__date__gte=first_of_month,
        visit_date__date__lte=today,
    ).count()

    context = {
        'total_patients': total_patients,
        'today_visits': today_visits,
        'month_visits': month_visits,
    }
    return render(request, 'patients/dashboard.html', context)


# ─────────────────────────── AJAX Search ─────────────────────────────────────

@doctor_required
@require_GET
def search_patients(request):
    query = request.GET.get('q', '').strip()
    results = []

    if len(query) >= 2:
        # Single query with Q objects instead of Python OR on two querysets
        patients = (
            Patient.objects
            .filter(doctor=request.user)
            .filter(Q(name__icontains=query) | Q(phone__icontains=query))
            .only('id', 'name', 'phone', 'gender', 'date_of_birth')
            .distinct()[:10]
        )

        for p in patients:
            # last_visit is acceptable here — small bounded result set (max 10)
            last_visit = p.last_visit
            results.append({
                'id': p.id,
                'name': p.name,
                'phone': p.phone,
                'age': p.age,
                'last_visit_date': (
                    last_visit.visit_date.strftime('%Y-%m-%d') if last_visit else None
                ),
            })

    return JsonResponse({'results': results, 'query': query})


# ─────────────────────────── Patient List ─────────────────────────────────────

@doctor_required
def patient_list(request):
    qs = Patient.objects.filter(doctor=request.user)
    query = request.GET.get('q', '').strip()
    gender_filter = request.GET.get('gender', '').strip()

    if query:
        # Single query with Q objects — no Python OR on two separate querysets
        qs = qs.filter(Q(name__icontains=query) | Q(phone__icontains=query))

    if gender_filter in ('male', 'female'):
        qs = qs.filter(gender=gender_filter)

    # Order first without annotations so pagination count is just a simple COUNT(*)
    qs = qs.order_by('-created_at')
    
    total_patients_count = qs.count()
    
    # Optional: total visits for the filtered patients
    total_visits_count = Visit.objects.filter(patient__in=qs).count()

    paginator = Paginator(qs, 10)  # Changed to 10 for easier visual testing
    page_num = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_num)

    # Re-fetch the paginated subset with annotations to avoid N+1 and heavy grouping on all rows
    page_ids = [p.id for p in page_obj.object_list]
    if page_ids:
        annotated_patients = (
            Patient.objects.filter(id__in=page_ids)
            .annotate(
                visit_count=Count('visits'),
                last_visit_date=Max('visits__visit_date')
            )
        )
        annotated_map = {p.id: p for p in annotated_patients}
        page_obj.object_list = [annotated_map[pid] for pid in page_ids if pid in annotated_map]

    context = {
        'page_obj': page_obj,
        'query': query,
        'gender_filter': gender_filter,
        'total_patients_count': total_patients_count,
        'total_visits_count': total_visits_count,
    }
    return render(request, 'patients/patient_list.html', context)


# ─────────────────────────── Patient Detail ───────────────────────────────────

@doctor_required
def patient_detail(request, pk):
    patient = get_object_or_404(Patient, pk=pk, doctor=request.user)
    visits_qs = (
        Visit.objects.filter(patient=patient)
        .only('id', 'visit_date', 'chief_complaint', 'diagnosis', 'created_at', 'next_checkup_date')
        .prefetch_related('files')
        .order_by('-visit_date')
    )
    paginator = Paginator(visits_qs, 10)
    page_num = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_num)

    context = {
        'patient': patient,
        'page_obj': page_obj,
    }
    return render(request, 'patients/patient_detail.html', context)


@doctor_required
def patient_files(request, pk):
    patient = get_object_or_404(Patient, pk=pk, doctor=request.user)
    
    # Get all files and links for this patient, grouped by visit
    files = VisitFile.objects.filter(
        visit__patient=patient
    ).select_related('visit').order_by('-visit__visit_date', '-uploaded_at')
    
    context = {
        'patient': patient,
        'files': files,
    }
    return render(request, 'patients/patient_files.html', context)


# ─────────────────────────── Add / Edit Patient ───────────────────────────────

@doctor_required
def add_patient(request):
    if request.method == 'POST':
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            patient = Patient(doctor=request.user)
            error = _fill_patient_from_post(patient, request.POST)
            if error:
                return JsonResponse({'success': False, 'message': error})
            patient.save()
            return JsonResponse({
                'success': True,
                'message': f'Patient "{patient.name}" added successfully.',
                'patient_id': patient.pk,
                'patient_name': patient.name,
                'patient_phone': patient.phone,
                'patient_gender': patient.gender,
                'patient_dob': str(patient.date_of_birth) if patient.date_of_birth else None,
            })
        patient = Patient(doctor=request.user)
        error = _fill_patient_from_post(patient, request.POST)
        if error:
            messages.error(request, error)
            return render(request, 'patients/patient_form.html', {'action': 'Add', 'patient': None})
        patient.save()
        messages.success(request, f'Patient "{patient.name}" added successfully.')
        return redirect('patient_detail', pk=patient.pk)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'patients/patient_form.html', {'action': 'Add', 'patient': None})

    return render(request, 'patients/patient_form.html', {'action': 'Add', 'patient': None})


@doctor_required
def edit_patient(request, pk):
    patient = get_object_or_404(Patient, pk=pk, doctor=request.user)

    if request.method == 'POST':
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            error = _fill_patient_from_post(patient, request.POST)
            if error:
                return JsonResponse({'success': False, 'message': error})
            patient.save()
            return JsonResponse({
                'success': True,
                'message': f'Patient "{patient.name}" updated.',
                'patient_id': patient.pk,
                'patient_name': patient.name,
                'patient_phone': patient.phone,
                'patient_gender': patient.gender,
                'patient_dob': str(patient.date_of_birth) if patient.date_of_birth else None,
            })
        error = _fill_patient_from_post(patient, request.POST)
        if error:
            messages.error(request, error)
            return render(request, 'patients/patient_form.html', {'action': 'Edit', 'patient': patient})
        patient.save()
        messages.success(request, f'Patient "{patient.name}" updated.')
        return redirect('patient_detail', pk=patient.pk)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'patients/patient_form.html', {'action': 'Edit', 'patient': patient})

    return render(request, 'patients/patient_form.html', {'action': 'Edit', 'patient': patient})


@doctor_required
def delete_patient(request, pk):
    patient = get_object_or_404(Patient, pk=pk, doctor=request.user)
    if request.method == 'POST':
        name = patient.name
        patient.delete()
        return JsonResponse({'success': True, 'message': f'Patient "{name}" deleted.'})
    return JsonResponse({'success': False, 'message': 'Method not allowed.'}, status=405)


def _fill_patient_from_post(patient, post):
    """
    Fills a Patient instance from POST data.
    Returns an error string on validation failure, or None on success.
    """
    name = post.get('name', '').strip()[:200]
    if not name:
        return 'Patient name is required.'

    patient.name = name
    patient.phone = post.get('phone', '').strip()[:20]
    dob = post.get('date_of_birth', '').strip()
    if dob:
        parsed_dob = parse_date(dob)
        patient.date_of_birth = parsed_dob if parsed_dob else None
    else:
        patient.date_of_birth = None
    gender = post.get('gender', 'male')
    patient.gender = gender if gender in ('male', 'female') else 'male'
    patient.notes = post.get('notes', '').strip()
    return None
def _safe_date(value):
    # Parse a string to date safely; returns None on failure.
    if not value or not value.strip():
        return None
    try:
        return parse_date(value.strip())
    except (ValueError, TypeError):
        return None



# ─────────────────────────── Add Visit ────────────────────────────────────────

@doctor_required
def add_visit(request, pk):
    patient = get_object_or_404(Patient, pk=pk, doctor=request.user)

    if request.method == 'POST':
        # Collect all clinical fields
        fields_to_check = [
            request.POST.get('chief_complaint', '').strip(),
            request.POST.get('symptoms', '').strip(),
            request.POST.get('diagnosis', '').strip(),
            request.POST.get('treatment', '').strip(),
            request.POST.get('temperature', '').strip(),
            request.POST.get('blood_pressure', '').strip(),
            request.POST.get('pulse', '').strip(),
            request.POST.get('weight', '').strip(),
        ]
        
        # Check if at least one field is filled
        if not any(fields_to_check):
            messages.error(request, 'Please fill at least one clinical field to save the visit.')
            return render(request, 'patients/add_visit.html', {
                'patient': patient,
                'post': request.POST,
                'visit': Visit(patient=patient, doctor=request.user),
                'is_edit': False,
            })
        
        chief_complaint = request.POST.get('chief_complaint', '').strip()

        # Parse visit date safely
        visit_date_str = request.POST.get('visit_date', '').strip()
        visit_date = parse_datetime(visit_date_str) if visit_date_str else None
        if visit_date is None:
            visit_date = timezone.now()

        visit = Visit(
            patient=patient,
            doctor=request.user,
            visit_date=visit_date,
            chief_complaint=chief_complaint,
            symptoms=request.POST.get('symptoms', '').strip() or None,
            diagnosis=request.POST.get('diagnosis', '').strip() or None,
            treatment=request.POST.get('treatment', '').strip() or None,
            blood_pressure=request.POST.get('blood_pressure', '').strip(),
            doctor_notes=request.POST.get('doctor_notes', '').strip() or None,
        )

        # Validate and assign numeric vitals
        visit.temperature = _safe_decimal(request.POST.get('temperature'))
        visit.pulse = _safe_int(request.POST.get('pulse'))
        visit.weight = _safe_decimal(request.POST.get('weight'))

        visit.next_checkup_date = _safe_date(request.POST.get('next_checkup_date'))

        visit.save()

        # ── File uploads ─────────────────────────────────────────────────────
        titles = request.POST.getlist('file_title')
        file_types = request.POST.getlist('file_type')
        file_notes_list = request.POST.getlist('file_notes')
        files = request.FILES.getlist('visit_files')

        valid_file_types = {ft[0] for ft in VisitFile.FILE_TYPE_CHOICES}
        file_errors = []

        for i, f in enumerate(files):
            # Extension check
            if '.' not in f.name:
                file_errors.append(f'"{f.name}": File has no extension.')
                continue
            ext = '.' + f.name.rsplit('.', 1)[-1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                file_errors.append(f'"{f.name}": Only JPG, PNG, and PDF files are allowed.')
                continue
            # Size check
            if f.size > MAX_FILE_SIZE:
                file_errors.append(f'"{f.name}": File too large. Maximum size is 10 MB.')
                continue

            title = (titles[i] if i < len(titles) else '').strip() or f.name
            ftype = file_types[i] if i < len(file_types) else 'other'
            if ftype not in valid_file_types:
                ftype = 'other'
            fnotes = (file_notes_list[i] if i < len(file_notes_list) else '').strip()

            VisitFile.objects.create(
                visit=visit,
                doctor=request.user,
                title=title,
                file_type=ftype,
                file=f,
                notes=fnotes or None,
            )

        # ── Link uploads ─────────────────────────────────────────────────────
        link_urls = request.POST.getlist('link_url')
        link_titles = request.POST.getlist('link_title')
        link_types = request.POST.getlist('link_type')
        link_notes = request.POST.getlist('link_notes')

        for i, link in enumerate(link_urls):
            link = link.strip()
            if not link: continue
            title = (link_titles[i] if i < len(link_titles) else '').strip() or 'External Link'
            ftype = link_types[i] if i < len(link_types) else 'other'
            if ftype not in valid_file_types: ftype = 'other'
            fnotes = (link_notes[i] if i < len(link_notes) else '').strip()
            
            VisitFile.objects.create(
                visit=visit,
                doctor=request.user,
                title=title,
                file_type=ftype,
                link_url=link,
                notes=fnotes or None,
            )

        for err in file_errors:
            messages.warning(request, err)

        messages.success(request, 'Visit saved successfully.')
        return redirect('visit_detail', pk=visit.pk)

    context = {
        'patient': patient,
        'visit': Visit(patient=patient, doctor=request.user),
        'now': timezone.now(),
    }
    return render(request, 'patients/add_visit.html', context)


def _safe_decimal(value):
    """Parse a string to float/Decimal safely; returns None on failure."""
    try:
        v = str(value).strip()
        return float(v) if v else None
    except (ValueError, TypeError):
        return None


def _safe_int(value):
    """Parse a string to int safely; returns None on failure."""
    try:
        v = str(value).strip()
        return int(v) if v else None
    except (ValueError, TypeError):
        return None


# ─────────────────────────── Edit Visit ───────────────────────────────────────

@doctor_required
def edit_visit(request, pk):
    visit = get_object_or_404(Visit, pk=pk, doctor=request.user)
    patient = visit.patient

    if request.method == 'POST':
        # Collect all clinical fields
        fields_to_check = [
            request.POST.get('chief_complaint', '').strip(),
            request.POST.get('symptoms', '').strip(),
            request.POST.get('diagnosis', '').strip(),
            request.POST.get('treatment', '').strip(),
            request.POST.get('temperature', '').strip(),
            request.POST.get('blood_pressure', '').strip(),
            request.POST.get('pulse', '').strip(),
            request.POST.get('weight', '').strip(),
        ]
        
        if not any(fields_to_check):
            messages.error(request, 'Please fill at least one clinical field to save the visit.')
            return render(request, 'patients/add_visit.html', {
                'patient': patient,
                'visit': visit,
                'post': request.POST,
                'is_edit': True,
                'now': timezone.now()
            })
        
        chief_complaint = request.POST.get('chief_complaint', '').strip()

        visit_date_str = request.POST.get('visit_date', '').strip()
        if visit_date_str:
            parsed_date = parse_datetime(visit_date_str)
            if parsed_date: visit.visit_date = parsed_date
        
        visit.chief_complaint = chief_complaint
        visit.symptoms = request.POST.get('symptoms', '').strip() or None
        visit.diagnosis = request.POST.get('diagnosis', '').strip() or None
        visit.treatment = request.POST.get('treatment', '').strip() or None
        visit.blood_pressure = request.POST.get('blood_pressure', '').strip()
        visit.doctor_notes = request.POST.get('doctor_notes', '').strip() or None

        visit.temperature = _safe_decimal(request.POST.get('temperature'))
        visit.pulse = _safe_int(request.POST.get('pulse'))
        visit.weight = _safe_decimal(request.POST.get('weight'))

        visit.next_checkup_date = _safe_date(request.POST.get('next_checkup_date'))

        visit.save()

        # Handle new files/links...
        titles = request.POST.getlist('file_title')
        file_types = request.POST.getlist('file_type')
        file_notes_list = request.POST.getlist('file_notes')
        files = request.FILES.getlist('visit_files')

        valid_file_types = {ft[0] for ft in VisitFile.FILE_TYPE_CHOICES}
        
        for i, f in enumerate(files):
            title = (titles[i] if i < len(titles) else '').strip() or f.name
            ftype = file_types[i] if i < len(file_types) else 'other'
            fnotes = (file_notes_list[i] if i < len(file_notes_list) else '').strip()
            VisitFile.objects.create(visit=visit, doctor=request.user, title=title, file_type=ftype, file=f, notes=fnotes or None)

        link_urls = request.POST.getlist('link_url')
        link_titles = request.POST.getlist('link_title')
        link_types = request.POST.getlist('link_type')
        link_notes = request.POST.getlist('link_notes')

        for i, link in enumerate(link_urls):
            link = link.strip()
            if not link: continue
            title = (link_titles[i] if i < len(link_titles) else '').strip() or 'External Link'
            ftype = link_types[i] if i < len(link_types) else 'other'
            fnotes = (link_notes[i] if i < len(link_notes) else '').strip()
            VisitFile.objects.create(visit=visit, doctor=request.user, title=title, file_type=ftype, link_url=link, notes=fnotes or None)

        messages.success(request, 'Visit updated successfully.')
        return redirect('visit_detail', pk=visit.pk)

    context = {
        'patient': patient,
        'visit': visit,
        'is_edit': True,
        'now': timezone.now(),
    }
    return render(request, 'patients/add_visit.html', context)

# ─────────────────────────── Visit Detail ─────────────────────────────────────

@doctor_required
def visit_detail(request, pk):
    visit = get_object_or_404(
        Visit.objects.select_related('patient', 'doctor', 'doctor__doctor_profile'),
        pk=pk,
        doctor=request.user,
    )
    # Evaluate files once and split in Python — avoids 3 separate DB hits
    files = list(visit.files.all())
    context = {
        'visit': visit,
        'files': files,
        'images': [f for f in files if f.is_image],
        'pdfs': [f for f in files if f.is_pdf],
        'links': [f for f in files if f.is_link],
        'other_files': [f for f in files if not f.is_image and not f.is_pdf and not f.is_link],
    }
    return render(request, 'patients/visit_detail.html', context)


@doctor_required
def visit_print(request, pk):
    visit = get_object_or_404(
        Visit.objects.select_related('patient', 'doctor', 'doctor__doctor_profile'),
        pk=pk,
        doctor=request.user,
    )
    return render(request, 'patients/visit_print.html', {'visit': visit})


# ─────────────────────────── Delete Visit ─────────────────────────────────────

@doctor_required
def delete_visit(request, pk):
    visit = get_object_or_404(Visit, pk=pk, doctor=request.user)
    patient_pk = visit.patient_id
    if request.method == 'POST':
        visit.delete()
        return JsonResponse({'success': True, 'message': 'Visit deleted successfully.'})
    return JsonResponse({'success': False, 'message': 'Invalid request method.'})


# ─────────────────────────── Delete Visit File ────────────────────────────────

@doctor_required
def delete_visit_file(request, pk):
    vf = get_object_or_404(VisitFile, pk=pk, doctor=request.user)
    visit_pk = vf.visit_id  # Use _id to avoid extra query for the full Visit object
    if request.method == 'POST':
        # Delete the actual file from storage before removing the DB record
        vf.file.delete(save=False)
        vf.delete()
        messages.success(request, 'File deleted.')
        return redirect('visit_detail', pk=visit_pk)
    return render(request, 'patients/confirm_delete_file.html', {'file': vf})


@doctor_required
def upcoming_visits(request):
    """Shows patients with checkups scheduled for today and tomorrow."""
    today = timezone.localtime(timezone.now()).date()
    tomorrow = today + timezone.timedelta(days=1)

    today_checkups = (
        Patient.objects
        .filter(
            doctor=request.user,
            visits__next_checkup_date=today,
        )
        .select_related('doctor')
        .annotate(
            last_visit_date=Max('visits__visit_date'),
            visit_count=Count('visits'),
        )
        .order_by('name')
        .distinct()
    )

    tomorrow_checkups = (
        Patient.objects
        .filter(
            doctor=request.user,
            visits__next_checkup_date=tomorrow,
        )
        .select_related('doctor')
        .annotate(
            last_visit_date=Max('visits__visit_date'),
            visit_count=Count('visits'),
        )
        .order_by('name')
        .distinct()
    )

    # Get the actual Visit objects for each patient so we can show checkup details
    today_visits_map = {}
    for patient in today_checkups:
        visit = Visit.objects.filter(
            patient=patient,
            next_checkup_date=today,
        ).order_by('-visit_date').first()
        if visit:
            today_visits_map[patient.id] = visit

    tomorrow_visits_map = {}
    for patient in tomorrow_checkups:
        visit = Visit.objects.filter(
            patient=patient,
            next_checkup_date=tomorrow,
        ).order_by('-visit_date').first()
        if visit:
            tomorrow_visits_map[patient.id] = visit

    context = {
        'today_checkups': today_checkups,
        'tomorrow_checkups': tomorrow_checkups,
        'today_visits_map': today_visits_map,
        'tomorrow_visits_map': tomorrow_visits_map,
        'today_count': today_checkups.count(),
        'tomorrow_count': tomorrow_checkups.count(),
    }
    return render(request, 'patients/upcoming_visits.html', context)


# ─────────────────────────── Pending Visits ───────────────────────────────────

@doctor_required
def check_suggestions(request):
    """
    Receives transcribed text, applies personal corrections,
    and returns suggestions for potentially wrong words.
    """
    try:
        data = json.loads(request.body)
        text = data.get('text', '').strip()
        if not text:
            return JsonResponse({'error': 'No text provided'}, status=400)

        corrected_text, suggestions = find_suggestions(text, request.user)

        return JsonResponse({
            'success': True,
            'corrected_text': corrected_text,
            'suggestions': suggestions
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ─────────────────────────── Save Correction ──────────────────────────────────

@doctor_required
@require_POST
def save_correction(request):
    """
    Saves a confirmed correction to the doctor's personal learning table.
    Next time the same wrong word appears, it gets auto-corrected.
    """
    try:
        data = json.loads(request.body)
        wrong_word = data.get('wrong_word', '').strip()
        correct_word = data.get('correct_word', '').strip()

        if not wrong_word or not correct_word:
            return JsonResponse({'error': 'Both wrong_word and correct_word are required'}, status=400)

        correction, created = TranscriptionCorrection.objects.get_or_create(
            doctor=request.user,
            wrong_word=wrong_word,
            defaults={'correct_word': correct_word}
        )

        if not created:
            correction.correct_word = correct_word
            correction.usage_count += 1
            correction.save()

        # Also add the correct word to dictionary if not already there
        MedicalDictionary.objects.get_or_create(
            word=correct_word,
            defaults={'category': 'other'}
        )

        # Invalidate dictionary cache
        cache.delete('medical_dictionary_words')

        return JsonResponse({
            'success': True,
            'message': f'Correction saved: {wrong_word} → {correct_word}',
            'usage_count': correction.usage_count
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ───────────────────────── Groq Transcription ─────────────────────────

import tempfile
from django.conf import settings as django_settings
from groq import Groq as _Groq

MEDICAL_PROMPT = (
    "amlodipine, metformin, atorvastatin, paracetamol, amoxicillin, "
    "diclofenac, meloxicam, dexamethasone, omeprazole, losartan, "
    "metoclopramide, prednisolone, ciprofloxacin, azithromycin, ibuprofen, "
    "blood pressure, diabetes, hypertension, gastritis, infection, "
    "antibiotics, antihistamine, corticosteroid, antacid, analgesic, "
    "\u0623\u0645\u0644\u0648\u062f\u064a\u0628\u064a\u0646, \u0645\u064a\u062a\u0641\u0648\u0631\u0645\u064a\u0646, \u0628\u0646\u0627\u062f\u0648\u0644, \u0623\u0645\u0648\u0643\u0633\u064a\u0633\u064a\u0644\u064a\u0646, "
    "\u062f\u064a\u0643\u0644\u0648\u0641\u064a\u0646\u0627\u0643, \u0645\u064a\u0644\u0648\u0643\u0633\u064a\u0643\u0627\u0645, \u062f\u064a\u0643\u0633\u0627\u0645\u064a\u062b\u0627\u0632\u0648\u0646, \u0623\u0648\u0645\u0628\u0631\u0627\u0632\u0648\u0644, \u0644\u0648\u0633\u0627\u0631\u062a\u0627\u0646"
)



PARSE_SYSTEM_PROMPT = """
You are a medical transcript parser for an Egyptian doctor's clinic system.
You will receive an Arabic/mixed Arabic-English transcript of a doctor dictating a patient visit.
The doctor uses specific Arabic trigger words to indicate which field he is filling.

Parse the transcript and extract content for these fields:
- chief_complaint: triggered by (شكوى، الشكوى، شكوة)
- symptoms: triggered by (أعراض، الأعراض، علامات)
- diagnosis: triggered by (تشخيص، التشخيص، تشخيصي)
- treatment: triggered by (علاج، العلاج، وصفة، الوصفة، دواء)
- doctor_notes: triggered by (ملاحظات، ملاحظات خاصة، نوت، نوتس)
- temperature: triggered by (حرارة، درجة الحرارة). Extract only the number.
- blood_pressure: triggered by (ضغط، الضغط). Extract as text (e.g. 120/80).
- pulse: triggered by (نبض، النبض، دقات القلب). Extract only the number.
- weight: triggered by (وزن، الوزن). Extract only the number.
- next_checkup_date: triggered by (استشارة، موعد القادم، استشارة بعد، استشارة في). Format: YYYY-MM-DD. (IMPORTANT: Must be in YYYY-MM-DD format, e.g., 2026-12-31. If you hear "after 2 weeks", calculate the date from today which is 2026-04-12)

Rules:
- Extract ONLY what the doctor said for each field, nothing else
- If a field was not mentioned, return empty string "" for it
- Keep medical drug names exactly as spoken
- Keep the text in the same language the doctor used (Arabic, English, or mixed)
- If blood_pressure field contains "على" between two numbers, convert to "/" format. Example: "120 على 80" → "120/80"
- Do NOT translate, summarize, or modify the content
- Return ONLY a valid JSON object with no extra text, no markdown, no explanation

Return format:
{
  "chief_complaint": "...",
  "symptoms": "...",
  "diagnosis": "...",
  "treatment": "...",
  "doctor_notes": "...",
  "temperature": "...",
  "blood_pressure": "...",
  "pulse": "...",
  "weight": "...",
  "next_checkup_date": "..."
}
"""

@doctor_required
@require_POST
def transcribe_and_parse(request):
    audio_file = request.FILES.get('audio')
    if not audio_file:
        return JsonResponse({'error': 'No audio file received'}, status=400)

    suffix = '.webm'
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            for chunk in audio_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        # Step 1: Transcribe with Groq
        if not django_settings.GROQ_API_KEY:
            return JsonResponse({'error': 'GROQ API Key is missing. Please add GROQ_API_KEY to your .env file.'}, status=500)
        groq_client = _Groq(api_key=django_settings.GROQ_API_KEY)
        try:
            with open(tmp_path, 'rb') as f:
                transcription = groq_client.audio.transcriptions.create(
                    file=(os.path.basename(tmp_path), f),
                    model='whisper-large-v3',
                    prompt=MEDICAL_PROMPT,
                    response_format='text',
                    timeout=30
                )
        except Exception as e:
            return JsonResponse({'error': f'Transcription failed: {str(e)}'}, status=500)
        raw_transcript = transcription.strip()
        raw_transcript = re.sub(r'(\d+)\s*على\s*(\d+)', r'\1/\2', raw_transcript) # Fix Arabic BP
        if not raw_transcript:
            return JsonResponse({'error': 'Empty transcript'}, status=400)

        # Apply personal learned corrections before parsing
        raw_transcript = apply_personal_corrections(raw_transcript, request.user)

        # Step 2: Parse with Multi-Layer Fallback
        parsed_fields = None
        fallback_used = False
        
        try:
            # Layer 1: Groq Llama (Primary)
            completion = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": f"{PARSE_SYSTEM_PROMPT}\n\nIMPORTANT: Output ONLY a valid JSON object."},
                    {"role": "user", "content": f"Parse this medical transcript into fields:\n\n{raw_transcript}"}
                ],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            response_text = completion.choices[0].message.content.strip()
            response_text = response_text.replace('```json', '').replace('```', '').strip()
            parsed_fields = json.loads(response_text)
            
        except Exception as groq_err:
            # Groq parse failed: fall back to local regex (no OpenAI)
            parsed_fields = regex_parse_transcript(raw_transcript)
            fallback_used = True

        return JsonResponse({
            'success': True,
            'transcript': raw_transcript,
            'fields': parsed_fields,
            'fallback_used': fallback_used
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Failed to parse fields from transcript'}, status=500)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ─────────────────────────── Transcribe Patient Info ────────────────────────────

PATIENT_PARSE_SYSTEM_PROMPT = """
You are a medical transcript parser for an Egyptian doctor's clinic system.
You will receive an Arabic/mixed Arabic-English transcript of a doctor dictating patient registration information.
The doctor uses specific Arabic trigger words to indicate which field he is filling.

Parse the transcript and extract content for these fields:
- name: triggered by (اسم، الاسم، اسم المريض، اسمه، اسمه المريض، اسمها، اسمها المريض)
- phone: triggered by (تليفون، هاتف، موبايل، رقم التليفون، رقم الهاتف، رقم الموبايل). Extract only the phone number.
- date_of_birth: triggered by (تاريخ الميلاد، يوم الميلاد، تاريخBirthday، Birthday). Format: YYYY-MM-DD.
- notes: triggered by (ملاحظات، notes، ملاحظات عامة، notes)

Rules:
- Extract ONLY what the doctor said for each field, nothing else
- If a field was not mentioned, return empty string "" for it
- Keep names exactly as spoken (in the same language)
- For phone numbers, extract only the digits. Egyptian numbers typically start with 01 followed by 0, 1, or 2.
- For date of birth, if you hear "born in year X" or "عمره X سنة", try to calculate birth year. Format: YYYY-MM-DD. If only year is known, use January 1.
- Return ONLY a valid JSON object with no extra text, no markdown, no explanation

Return format:
{
  "name": "...",
  "phone": "...",
  "date_of_birth": "...",
  "notes": "..."
}
"""


@doctor_required
@require_POST
def transcribe_patient_info(request):
    audio_file = request.FILES.get('audio')
    if not audio_file:
        return JsonResponse({'error': 'No audio file received'}, status=400)

    suffix = '.webm'
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            for chunk in audio_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        # Step 1: Transcribe with Groq
        if not django_settings.GROQ_API_KEY:
            return JsonResponse({'error': 'GROQ API Key is missing. Please add GROQ_API_KEY to your .env file.'}, status=500)
        groq_client = _Groq(api_key=django_settings.GROQ_API_KEY)
        try:
            with open(tmp_path, 'rb') as f:
                transcription = groq_client.audio.transcriptions.create(
                    file=(os.path.basename(tmp_path), f),
                    model='whisper-large-v3',
                    prompt=MEDICAL_PROMPT,
                    response_format='text',
                    timeout=30
                )
        except Exception as e:
            return JsonResponse({'error': f'Transcription failed: {str(e)}'}, status=500)
        raw_transcript = transcription.strip()
        if not raw_transcript:
            return JsonResponse({'error': 'Empty transcript'}, status=400)

        # Apply personal learned corrections before parsing
        raw_transcript = apply_personal_corrections(raw_transcript, request.user)

        # Step 2: Parse with Groq Llama
        parsed_fields = None
        fallback_used = False
        
        try:
            completion = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": f"{PATIENT_PARSE_SYSTEM_PROMPT}\n\nIMPORTANT: Output ONLY a valid JSON object."},
                    {"role": "user", "content": f"Parse this patient registration transcript into fields:\n\n{raw_transcript}"}
                ],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            response_text = completion.choices[0].message.content.strip()
            response_text = response_text.replace('```json', '').replace('```', '').strip()
            parsed_fields = json.loads(response_text)
            
        except Exception as groq_err:
            # Fall back to simple regex parsing
            parsed_fields = {
                'name': '',
                'phone': '',
                'date_of_birth': '',
                'notes': ''
            }
            # Simple keyword-based extraction
            import re as regex_re
            # Extract phone - Egyptian numbers
            phone_match = regex_re.search(r'01[012]\d{8}', raw_transcript)
            if phone_match:
                parsed_fields['phone'] = phone_match.group()
            # Extract notes
            notes_kw = ['ملاحظات', 'notes', 'ملاحظات عامة']
            for kw in notes_kw:
                idx = raw_transcript.lower().find(kw.lower())
                if idx != -1:
                    parsed_fields['notes'] = raw_transcript[idx + len(kw):].strip()
                    break
            fallback_used = True

        return JsonResponse({
            'success': True,
            'transcript': raw_transcript,
            'fields': parsed_fields,
            'fallback_used': fallback_used
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Failed to parse fields from transcript'}, status=500)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
