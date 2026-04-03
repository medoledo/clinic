import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt

from accounts.decorators import doctor_required
from .models import Patient, Visit, VisitFile


# ─────────────────────────── Dashboard ──────────────────────────────

@doctor_required
def dashboard(request):
    today = timezone.now().date()
    first_of_month = today.replace(day=1)

    total_patients = Patient.objects.filter(doctor=request.user).count()
    today_visits = Visit.objects.filter(doctor=request.user, visit_date__date=today).count()
    month_visits = Visit.objects.filter(
        doctor=request.user,
        visit_date__date__gte=first_of_month,
        visit_date__date__lte=today,
    ).count()

    # Last 10 patients seen (by most recent visit)
    recent_visits = (
        Visit.objects.filter(doctor=request.user)
        .select_related('patient')
        .order_by('-visit_date')[:20]
    )
    seen_ids = []
    recent_patients = []
    for v in recent_visits:
        if v.patient_id not in seen_ids:
            seen_ids.append(v.patient_id)
            recent_patients.append(v.patient)
        if len(recent_patients) == 10:
            break

    context = {
        'total_patients': total_patients,
        'today_visits': today_visits,
        'month_visits': month_visits,
        'recent_patients': recent_patients,
    }
    return render(request, 'patients/dashboard.html', context)


# ─────────────────────────── AJAX Search ─────────────────────────────

@doctor_required
@require_GET
def search_patients(request):
    query = request.GET.get('q', '').strip()
    results = []

    if len(query) >= 2:
        patients = Patient.objects.filter(
            doctor=request.user,
            is_active=True,
        ).filter(
            name__icontains=query
        ) | Patient.objects.filter(
            doctor=request.user,
            is_active=True,
        ).filter(
            phone__icontains=query
        )
        patients = patients.distinct()[:10]

        for p in patients:
            last_visit = p.last_visit
            results.append({
                'id': p.id,
                'name': p.name,
                'phone': p.phone,
                'age': p.age,
                'last_visit_date': last_visit.visit_date.strftime('%Y-%m-%d') if last_visit else None,
            })

    return JsonResponse({'results': results, 'query': query})


# ─────────────────────────── Patient List ────────────────────────────

@doctor_required
def patient_list(request):
    qs = Patient.objects.filter(doctor=request.user)
    query = request.GET.get('q', '').strip()
    gender_filter = request.GET.get('gender', '')

    if query:
        qs = qs.filter(name__icontains=query) | qs.filter(phone__icontains=query)
        qs = qs.distinct()

    if gender_filter in ('male', 'female'):
        qs = qs.filter(gender=gender_filter)

    paginator = Paginator(qs.order_by('-created_at'), 20)
    page_num = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_num)

    context = {
        'page_obj': page_obj,
        'query': query,
        'gender_filter': gender_filter,
    }
    return render(request, 'patients/patient_list.html', context)


# ─────────────────────────── Patient Detail ──────────────────────────

@doctor_required
def patient_detail(request, pk):
    patient = get_object_or_404(Patient, pk=pk, doctor=request.user)
    visits_qs = Visit.objects.filter(patient=patient).order_by('-visit_date')
    paginator = Paginator(visits_qs, 10)
    page_num = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_num)

    context = {
        'patient': patient,
        'page_obj': page_obj,
    }
    return render(request, 'patients/patient_detail.html', context)


# ─────────────────────────── Add Patient ─────────────────────────────

@doctor_required
def add_patient(request):
    if request.method == 'POST':
        patient = Patient(doctor=request.user)
        _fill_patient_from_post(patient, request.POST)
        patient.save()
        messages.success(request, f'Patient "{patient.name}" added successfully.')
        return redirect('patient_detail', pk=patient.pk)

    return render(request, 'patients/patient_form.html', {'action': 'Add', 'patient': None})


# ─────────────────────────── Edit Patient ────────────────────────────

@doctor_required
def edit_patient(request, pk):
    patient = get_object_or_404(Patient, pk=pk, doctor=request.user)

    if request.method == 'POST':
        _fill_patient_from_post(patient, request.POST)
        patient.save()
        messages.success(request, f'Patient "{patient.name}" updated.')
        return redirect('patient_detail', pk=patient.pk)

    return render(request, 'patients/patient_form.html', {'action': 'Edit', 'patient': patient})


def _fill_patient_from_post(patient, post):
    patient.name = post.get('name', '').strip()
    patient.phone = post.get('phone', '').strip()
    dob = post.get('date_of_birth', '').strip()
    patient.date_of_birth = dob if dob else None
    patient.gender = post.get('gender', 'male')
    patient.blood_type = post.get('blood_type', '').strip()
    patient.address = post.get('address', '').strip()
    patient.emergency_contact_name = post.get('emergency_contact_name', '').strip()
    patient.emergency_contact_phone = post.get('emergency_contact_phone', '').strip()
    patient.notes = post.get('notes', '').strip()
    patient.is_active = post.get('is_active') != 'off'


# ─────────────────────────── Add Visit ───────────────────────────────

ALLOWED_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.pdf')
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@doctor_required
def add_visit(request, pk):
    patient = get_object_or_404(Patient, pk=pk, doctor=request.user)

    if request.method == 'POST':
        chief_complaint = request.POST.get('chief_complaint', '').strip()
        if not chief_complaint:
            messages.error(request, 'Chief complaint is required.')
            return render(request, 'patients/add_visit.html', {
                'patient': patient,
                'post': request.POST,
            })

        visit_date_str = request.POST.get('visit_date', '').strip()
        try:
            from django.utils.dateparse import parse_datetime
            visit_date = parse_datetime(visit_date_str) if visit_date_str else timezone.now()
            if visit_date is None:
                visit_date = timezone.now()
        except Exception:
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

        try:
            temp = request.POST.get('temperature', '').strip()
            visit.temperature = float(temp) if temp else None
        except ValueError:
            visit.temperature = None

        try:
            pulse = request.POST.get('pulse', '').strip()
            visit.pulse = int(pulse) if pulse else None
        except ValueError:
            visit.pulse = None

        try:
            weight = request.POST.get('weight', '').strip()
            visit.weight = float(weight) if weight else None
        except ValueError:
            visit.weight = None

        ncd = request.POST.get('next_checkup_date', '').strip()
        visit.next_checkup_date = ncd if ncd else None

        visit.save()

        # Handle file uploads
        titles = request.POST.getlist('file_title')
        file_types = request.POST.getlist('file_type')
        file_notes_list = request.POST.getlist('file_notes')
        files = request.FILES.getlist('visit_files')

        file_errors = []
        for i, f in enumerate(files):
            ext = '.' + f.name.rsplit('.', 1)[-1].lower() if '.' in f.name else ''
            if ext not in ALLOWED_EXTENSIONS:
                file_errors.append(f'"{f.name}": Only JPG, PNG, and PDF files are allowed.')
                continue
            if f.size > MAX_FILE_SIZE:
                file_errors.append(f'"{f.name}": File too large. Maximum size is 10MB.')
                continue

            title = titles[i] if i < len(titles) else f.name
            ftype = file_types[i] if i < len(file_types) else 'other'
            fnotes = file_notes_list[i] if i < len(file_notes_list) else ''

            VisitFile.objects.create(
                visit=visit,
                doctor=request.user,
                title=title or f.name,
                file_type=ftype,
                file=f,
                notes=fnotes or None,
            )

        for err in file_errors:
            messages.warning(request, err)

        messages.success(request, 'Visit saved successfully.')
        return redirect('visit_detail', pk=visit.pk)

    context = {
        'patient': patient,
        'now': timezone.now(),
    }
    return render(request, 'patients/add_visit.html', context)


# ─────────────────────────── Visit Detail ────────────────────────────

@doctor_required
def visit_detail(request, pk):
    visit = get_object_or_404(Visit, pk=pk, doctor=request.user)
    files = visit.files.all()
    context = {
        'visit': visit,
        'files': files,
        'images': [f for f in files if f.is_image],
        'pdfs': [f for f in files if f.is_pdf],
        'other_files': [f for f in files if not f.is_image and not f.is_pdf],
    }
    return render(request, 'patients/visit_detail.html', context)


@doctor_required
def visit_print(request, pk):
    visit = get_object_or_404(Visit, pk=pk, doctor=request.user)
    return render(request, 'patients/visit_print.html', {'visit': visit})


# ─────────────────────────── Delete Visit File ───────────────────────

@doctor_required
def delete_visit_file(request, pk):
    vf = get_object_or_404(VisitFile, pk=pk, doctor=request.user)
    visit_pk = vf.visit.pk
    if request.method == 'POST':
        vf.file.delete(save=False)
        vf.delete()
        messages.success(request, 'File deleted.')
        return redirect('visit_detail', pk=visit_pk)
    return render(request, 'patients/confirm_delete_file.html', {'file': vf})


# ─────────────────────────── Pending Visits ──────────────────────────

@doctor_required
def pending_visits(request):
    """Renders the pending (offline) visits page — actual data lives in IndexedDB."""
    return render(request, 'patients/pending_visits.html')


# ─────────────────────────── Sync Offline Visit ──────────────────────

@doctor_required
def sync_offline_visit(request):
    """Receives an offline-saved visit from JS and saves it to the DB."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
    except (ValueError, KeyError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    patient_id = data.get('patient_id')
    if not patient_id:
        return JsonResponse({'error': 'patient_id is required'}, status=400)

    patient = get_object_or_404(Patient, pk=patient_id, doctor=request.user)

    chief_complaint = data.get('chief_complaint', '').strip()
    if not chief_complaint:
        return JsonResponse({'error': 'chief_complaint is required'}, status=400)

    from django.utils.dateparse import parse_datetime
    visit_date_str = data.get('visit_date', '')
    visit_date = parse_datetime(visit_date_str) if visit_date_str else timezone.now()
    if visit_date is None:
        visit_date = timezone.now()

    visit = Visit.objects.create(
        patient=patient,
        doctor=request.user,
        visit_date=visit_date,
        chief_complaint=chief_complaint,
        symptoms=data.get('symptoms') or None,
        diagnosis=data.get('diagnosis') or None,
        treatment=data.get('treatment') or None,
        blood_pressure=data.get('blood_pressure', ''),
        doctor_notes=data.get('doctor_notes') or None,
        temperature=data.get('temperature') or None,
        pulse=data.get('pulse') or None,
        weight=data.get('weight') or None,
        next_checkup_date=data.get('next_checkup_date') or None,
    )

    return JsonResponse({
        'success': True,
        'visit_id': visit.pk,
        'offline_id': data.get('offline_id'),
    })
