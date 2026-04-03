from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta, datetime

from .models import UserProfile, DoctorProfile, AdminProfile
from .decorators import admin_required, doctor_required
from patients.models import Patient, Visit, VisitFile


def login_view(request):
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            if profile.role == 'admin':
                return redirect('admin_dashboard')
            elif profile.role == 'doctor':
                return redirect('dashboard')
        except UserProfile.DoesNotExist:
            pass

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        remember_me = request.POST.get('remember_me')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            if not user.is_active:
                messages.error(request, 'Your account has been deactivated. Contact admin.')
                return render(request, 'accounts/login.html')

            login(request, user)

            if remember_me:
                request.session.set_expiry(60 * 60 * 24 * 30)
            else:
                request.session.set_expiry(0)

            try:
                profile = user.profile
                if profile.role == 'admin':
                    return redirect('admin_dashboard')
                elif profile.role == 'doctor':
                    return redirect('dashboard')
            except UserProfile.DoesNotExist:
                pass

            messages.error(request, 'No role assigned to your account. Contact admin.')
            logout(request)
            return render(request, 'accounts/login.html')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'accounts/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


# ===== ADMIN VIEWS =====

@admin_required
def manage_doctors(request):
    today = timezone.now().date()
    this_month_start = today.replace(day=1)

    doctors = User.objects.filter(profile__role='doctor').select_related('profile', 'doctor_profile')
    doctors_data = []
    for doc in doctors:
        doc_profile = None
        try:
            doc_profile = doc.doctor_profile
        except DoctorProfile.DoesNotExist:
            pass
        doc_patients = Patient.objects.filter(doctor=doc).count()
        doc_visits = Visit.objects.filter(doctor=doc).count()
        doc_today = Visit.objects.filter(doctor=doc, visit_date__date=today).count()
        doc_this_month = Visit.objects.filter(doctor=doc, visit_date__date__gte=this_month_start).count()
        last_visit = Visit.objects.filter(doctor=doc).order_by('-visit_date').first()
        doctors_data.append({
            'user': doc,
            'profile': doc_profile,
            'patient_count': doc_patients,
            'visit_count': doc_visits,
            'today_visits': doc_today,
            'month_visits': doc_this_month,
            'last_active': last_visit.visit_date if last_visit else None,
        })
    doctors_data.sort(key=lambda x: x['visit_count'], reverse=True)

    total_doctors = len(doctors_data)
    active_doctors = sum(1 for d in doctors_data if d['user'].is_active)
    total_patients = Patient.objects.count()
    total_visits = Visit.objects.count()

    context = {
        'doctors_data': doctors_data,
        'total_doctors': total_doctors,
        'active_doctors': active_doctors,
        'total_patients': total_patients,
        'total_visits': total_visits,
    }
    return render(request, 'accounts/manage_doctors.html', context)


@admin_required
def admin_dashboard(request):
    today = timezone.now().date()
    this_week_start = today - timedelta(days=today.weekday())
    this_month_start = today.replace(day=1)
    last_month_end = this_month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    doctor_filter = request.GET.get('doctor_filter', '')

    all_doctors_qs = User.objects.filter(profile__role='doctor').select_related('profile')
    all_patients_qs = Patient.objects.all()
    all_visits_qs = Visit.objects.all()

    if doctor_filter:
        all_doctors_qs = all_doctors_qs.filter(pk=doctor_filter)
        all_patients_qs = all_patients_qs.filter(doctor_id=doctor_filter)
        all_visits_qs = all_visits_qs.filter(doctor_id=doctor_filter)

    total_doctors = all_doctors_qs.count()
    active_doctors = all_doctors_qs.filter(is_active=True).count()
    inactive_doctors = total_doctors - active_doctors

    total_patients = all_patients_qs.count()
    active_patients = all_patients_qs.filter(is_active=True).count()
    inactive_patients = total_patients - active_patients
    male_patients = all_patients_qs.filter(gender='male').count()
    female_patients = all_patients_qs.filter(gender='female').count()
    patients_with_visits = all_patients_qs.annotate(vc=Count('visits')).filter(vc__gt=0).count()
    patients_without_visits = total_patients - patients_with_visits

    blood_types = {}
    for bt_choice, bt_label in Patient._meta.get_field('blood_type').flatchoices:
        count = all_patients_qs.filter(blood_type=bt_choice).count()
        if count > 0:
            blood_types[bt_label] = count

    total_visits = all_visits_qs.count()
    today_visits = all_visits_qs.filter(visit_date__date=today).count()
    this_week_visits = all_visits_qs.filter(visit_date__date__gte=this_week_start).count()
    this_month_visits = all_visits_qs.filter(visit_date__date__gte=this_month_start).count()
    last_month_visits = Visit.objects.filter(
        visit_date__date__gte=last_month_start, visit_date__date__lte=last_month_end
    ).count()
    if doctor_filter:
        last_month_visits = Visit.objects.filter(
            doctor_id=doctor_filter, visit_date__date__gte=last_month_start, visit_date__date__lte=last_month_end
        ).count()

    if last_month_visits > 0:
        visit_growth = round(((this_month_visits - last_month_visits) / last_month_visits) * 100, 1)
    else:
        visit_growth = 0
    abs_visit_growth = abs(visit_growth)

    avg_visits_per_day = round(total_visits / max(1, (today - Visit.objects.order_by('visit_date').first().visit_date.date()).days + 1), 1) if total_visits > 0 else 0
    avg_visits_per_doctor = round(total_visits / max(1, total_doctors), 1)
    avg_visits_per_patient = round(total_visits / max(1, total_patients), 1)
    avg_patients_per_doctor = round(total_patients / max(1, total_doctors), 1)

    visits_with_files = all_visits_qs.annotate(fc=Count('files')).filter(fc__gt=0).count()
    visits_without_files = total_visits - visits_with_files

    visits_with_temp = all_visits_qs.exclude(temperature__isnull=True).count()
    visits_with_bp = all_visits_qs.exclude(blood_pressure__isnull=True).count()
    visits_with_pulse = all_visits_qs.exclude(pulse__isnull=True).count()
    visits_with_weight = all_visits_qs.exclude(weight__isnull=True).count()

    doctors_data = []
    for doc in all_doctors_qs:
        doc_patients = Patient.objects.filter(doctor=doc).count()
        doc_visits = Visit.objects.filter(doctor=doc).count()
        doc_today = Visit.objects.filter(doctor=doc, visit_date__date=today).count()
        doc_this_month = Visit.objects.filter(doctor=doc, visit_date__date__gte=this_month_start).count()
        last_visit = Visit.objects.filter(doctor=doc).order_by('-visit_date').first()
        doctors_data.append({
            'user': doc,
            'profile': doc.profile,
            'patient_count': doc_patients,
            'visit_count': doc_visits,
            'today_visits': doc_today,
            'month_visits': doc_this_month,
            'last_active': last_visit.visit_date if last_visit else None,
        })
    doctors_data.sort(key=lambda x: x['visit_count'], reverse=True)

    most_visited = Patient.objects.annotate(vc=Count('visits')).filter(vc__gt=0).order_by('-vc')[:10]
    most_visited_data = []
    for p in most_visited:
        last_v = Visit.objects.filter(patient=p).order_by('-visit_date').first()
        doctor_name = '—'
        if last_v:
            try:
                doctor_name = last_v.doctor.doctor_profile.full_name
            except DoctorProfile.DoesNotExist:
                doctor_name = last_v.doctor.username
        most_visited_data.append({
            'patient': p,
            'visit_count': p.vc,
            'last_visit': last_v.visit_date if last_v else None,
            'doctor': doctor_name,
        })

    no_visit_patients = all_patients_qs.annotate(vc=Count('visits')).filter(vc=0)[:10]

    recent_visits = all_visits_qs.select_related('patient', 'doctor').order_by('-visit_date')[:15]

    daily_breakdown = []
    for i in range(7):
        d = today - timedelta(days=6-i)
        day_visits = all_visits_qs.filter(visit_date__date=d).count()
        daily_breakdown.append({'date': d, 'day_name': d.strftime('%A'), 'visits': day_visits})

    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    weekday_data = []
    for i, name in enumerate(day_names):
        django_day = i + 2 if i < 6 else 1
        wd_visits = all_visits_qs.filter(visit_date__week_day=django_day).count()
        weekday_data.append({'name': name, 'visits': wd_visits})
    weekday_data.sort(key=lambda x: x['visits'], reverse=True)
    busiest_day = weekday_data[0]['name'] if weekday_data else '—'

    context = {
        'doctor_filter': doctor_filter,
        'all_doctors': User.objects.filter(profile__role='doctor').select_related('profile'),
        'total_doctors': total_doctors,
        'active_doctors': active_doctors,
        'inactive_doctors': inactive_doctors,
        'total_patients': total_patients,
        'active_patients': active_patients,
        'inactive_patients': inactive_patients,
        'male_patients': male_patients,
        'female_patients': female_patients,
        'patients_with_visits': patients_with_visits,
        'patients_without_visits': patients_without_visits,
        'blood_types': blood_types,
        'total_visits': total_visits,
        'today_visits': today_visits,
        'this_week_visits': this_week_visits,
        'this_month_visits': this_month_visits,
        'last_month_visits': last_month_visits,
        'visit_growth': visit_growth,
        'abs_visit_growth': abs_visit_growth,
        'avg_visits_per_day': avg_visits_per_day,
        'avg_visits_per_doctor': avg_visits_per_doctor,
        'avg_visits_per_patient': avg_visits_per_patient,
        'avg_patients_per_doctor': avg_patients_per_doctor,
        'visits_with_files': visits_with_files,
        'visits_without_files': visits_without_files,
        'visits_with_temp': visits_with_temp,
        'visits_with_bp': visits_with_bp,
        'visits_with_pulse': visits_with_pulse,
        'visits_with_weight': visits_with_weight,
        'doctors_data': doctors_data,
        'most_visited_data': most_visited_data,
        'no_visit_patients': no_visit_patients,
        'recent_visits': recent_visits,
        'daily_breakdown': daily_breakdown,
        'weekday_data': weekday_data,
        'busiest_day': busiest_day,
    }
    return render(request, 'accounts/admin_dashboard.html', context)


@admin_required
def add_doctor(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        full_name = request.POST.get('full_name', '').strip()
        specialization = request.POST.get('specialization', '').strip()
        phone = request.POST.get('phone', '').strip()
        is_active = request.POST.get('is_active') == 'on'

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already taken. Please choose another.')
            return render(request, 'accounts/doctor_form.html', {'action': 'Add'})

        user = User.objects.create_user(
            username=username,
            password=password,
            is_active=is_active,
        )
        UserProfile.objects.create(user=user, role='doctor')
        DoctorProfile.objects.create(
            user=user,
            full_name=full_name,
            specialization=specialization,
            phone=phone,
        )
        messages.success(request, f'Doctor "{full_name}" added successfully.')
        return redirect('manage_doctors')

    return render(request, 'accounts/doctor_form.html', {'action': 'Add'})


@admin_required
def edit_doctor(request, pk):
    doctor_user = get_object_or_404(User, pk=pk, profile__role='doctor')
    try:
        profile = doctor_user.doctor_profile
    except DoctorProfile.DoesNotExist:
        profile = None

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        specialization = request.POST.get('specialization', '').strip()
        phone = request.POST.get('phone', '').strip()
        is_active = request.POST.get('is_active') == 'on'

        if profile:
            profile.full_name = full_name
            profile.specialization = specialization
            profile.phone = phone
            profile.save()

        doctor_user.is_active = is_active
        doctor_user.save()

        messages.success(request, f'Doctor "{full_name}" updated successfully.')
        return redirect('manage_doctors')

    context = {
        'action': 'Edit',
        'doctor_user': doctor_user,
        'profile': profile,
    }
    return render(request, 'accounts/doctor_form.html', context)


@admin_required
def reset_doctor_password(request, pk):
    doctor_user = get_object_or_404(User, pk=pk, profile__role='doctor')
    full_name = doctor_user.username
    try:
        full_name = doctor_user.doctor_profile.full_name
    except DoctorProfile.DoesNotExist:
        pass

    if request.method == 'POST':
        new_password = request.POST.get('new_password', '').strip()
        if new_password:
            doctor_user.set_password(new_password)
            doctor_user.save()
            messages.success(request, f'Password for "{full_name}" reset successfully.')
        else:
            messages.error(request, 'Password cannot be empty.')
        return redirect('manage_doctors')

    return render(request, 'accounts/reset_password.html', {'doctor_user': doctor_user})


@admin_required
def toggle_doctor_status(request, pk):
    doctor_user = get_object_or_404(User, pk=pk, profile__role='doctor')
    doctor_user.is_active = not doctor_user.is_active
    doctor_user.save()
    status = 'activated' if doctor_user.is_active else 'deactivated'
    full_name = doctor_user.username
    try:
        full_name = doctor_user.doctor_profile.full_name
    except DoctorProfile.DoesNotExist:
        pass
    messages.success(request, f'Doctor "{full_name}" {status}.')
    return redirect('manage_doctors')


@admin_required
def delete_doctor(request, pk):
    doctor_user = get_object_or_404(User, pk=pk, profile__role='doctor')
    patient_count = Patient.objects.filter(doctor=doctor_user).count()

    if patient_count > 0:
        messages.error(
            request,
            f'Cannot delete doctor — they have {patient_count} patient(s). Deactivate them instead.'
        )
        return redirect('manage_doctors')

    if request.method == 'POST':
        full_name = doctor_user.username
        try:
            full_name = doctor_user.doctor_profile.full_name
        except DoctorProfile.DoesNotExist:
            pass
        doctor_user.delete()
        messages.success(request, f'Doctor "{full_name}" deleted successfully.')
        return redirect('manage_doctors')

    return render(request, 'accounts/confirm_delete.html', {'doctor_user': doctor_user})


# ===== DOCTOR VIEWS =====

@doctor_required
def dashboard(request):
    today = timezone.now().date()
    doctor = request.user

    total_patients = Patient.objects.filter(doctor=doctor).count()
    today_visits = Visit.objects.filter(doctor=doctor, visit_date__date=today).count()
    month_start = today.replace(day=1)
    month_visits = Visit.objects.filter(doctor=doctor, visit_date__date__gte=month_start).count()

    recent_patients = Patient.objects.filter(
        doctor=doctor, visits__isnull=False
    ).distinct().order_by('-visits__visit_date')[:10]

    context = {
        'total_patients': total_patients,
        'today_visits': today_visits,
        'month_visits': month_visits,
        'recent_patients': recent_patients,
    }
    return render(request, 'patients/dashboard.html', context)


@doctor_required
def patient_list(request):
    doctor = request.user
    patients = Patient.objects.filter(doctor=doctor).select_related('doctor')

    from django.core.paginator import Paginator
    paginator = Paginator(patients, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
    }
    return render(request, 'patients/patient_list.html', context)


@doctor_required
def patient_detail(request, pk):
    doctor = request.user
    patient = get_object_or_404(Patient, pk=pk, doctor=doctor)
    visits = patient.visits.all().order_by('-visit_date')

    from django.core.paginator import Paginator
    paginator = Paginator(visits, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'patient': patient,
        'page_obj': page_obj,
    }
    return render(request, 'patients/patient_detail.html', context)


@doctor_required
def add_patient(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        phone = request.POST.get('phone', '').strip()
        date_of_birth = request.POST.get('date_of_birth', '').strip() or None
        gender = request.POST.get('gender', 'male')
        blood_type = request.POST.get('blood_type', '').strip()
        address = request.POST.get('address', '').strip()
        emergency_contact_name = request.POST.get('emergency_contact_name', '').strip()
        emergency_contact_phone = request.POST.get('emergency_contact_phone', '').strip()
        notes = request.POST.get('notes', '').strip()

        patient = Patient.objects.create(
            doctor=request.user,
            name=name,
            phone=phone,
            date_of_birth=date_of_birth,
            gender=gender,
            blood_type=blood_type,
            address=address,
            emergency_contact_name=emergency_contact_name,
            emergency_contact_phone=emergency_contact_phone,
            notes=notes,
        )
        messages.success(request, f'Patient "{name}" added successfully.')
        return redirect('patient_detail', pk=patient.pk)

    return render(request, 'patients/add_patient.html')


@doctor_required
def edit_patient(request, pk):
    doctor = request.user
    patient = get_object_or_404(Patient, pk=pk, doctor=doctor)

    if request.method == 'POST':
        patient.name = request.POST.get('name', '').strip()
        patient.phone = request.POST.get('phone', '').strip()
        patient.date_of_birth = request.POST.get('date_of_birth', '').strip() or None
        patient.gender = request.POST.get('gender', 'male')
        patient.blood_type = request.POST.get('blood_type', '').strip()
        patient.address = request.POST.get('address', '').strip()
        patient.emergency_contact_name = request.POST.get('emergency_contact_name', '').strip()
        patient.emergency_contact_phone = request.POST.get('emergency_contact_phone', '').strip()
        patient.notes = request.POST.get('notes', '').strip()
        patient.save()

        messages.success(request, f'Patient "{patient.name}" updated successfully.')
        return redirect('patient_detail', pk=patient.pk)

    return render(request, 'patients/add_patient.html', {'patient': patient})


@doctor_required
def add_visit(request, patient_pk):
    doctor = request.user
    patient = get_object_or_404(Patient, pk=patient_pk, doctor=doctor)

    if request.method == 'POST':
        chief_complaint = request.POST.get('chief_complaint', '').strip()

        if not chief_complaint:
            messages.error(request, 'Chief complaint is required.')
            return render(request, 'patients/add_visit.html', {'patient': patient})

        visit = Visit.objects.create(
            patient=patient,
            doctor=doctor,
            visit_date=request.POST.get('visit_date') or timezone.now(),
            chief_complaint=chief_complaint,
            symptoms=request.POST.get('symptoms', '').strip() or None,
            diagnosis=request.POST.get('diagnosis', '').strip() or None,
            treatment=request.POST.get('treatment', '').strip() or None,
            temperature=request.POST.get('temperature', '').strip() or None,
            blood_pressure=request.POST.get('blood_pressure', '').strip() or None,
            pulse=request.POST.get('pulse', '').strip() or None,
            weight=request.POST.get('weight', '').strip() or None,
            next_checkup_date=request.POST.get('next_checkup_date', '').strip() or None,
            doctor_notes=request.POST.get('doctor_notes', '').strip() or None,
        )

        files = request.FILES.getlist('files')
        file_titles = request.POST.getlist('file_title')
        file_types = request.POST.getlist('file_type')
        file_notes = request.POST.getlist('file_notes')

        for i, f in enumerate(files):
            if i < len(file_titles) and file_titles[i].strip():
                VisitFile.objects.create(
                    visit=visit,
                    doctor=doctor,
                    title=file_titles[i].strip(),
                    file_type=file_types[i] if i < len(file_types) else 'other',
                    file=f,
                    notes=file_notes[i].strip() if i < len(file_notes) else None,
                )

        messages.success(request, 'Visit saved successfully.')
        return redirect('visit_detail', pk=visit.pk)

    return render(request, 'patients/add_visit.html', {'patient': patient})


@doctor_required
def visit_detail(request, pk):
    doctor = request.user
    visit = get_object_or_404(Visit, pk=pk, doctor=doctor)
    files = visit.files.all()
    images = [f for f in files if f.is_image]
    pdfs = [f for f in files if f.is_pdf]

    context = {
        'visit': visit,
        'files': files,
        'images': images,
        'pdfs': pdfs,
    }
    return render(request, 'patients/visit_detail.html', context)


@doctor_required
def delete_visit_file(request, pk):
    doctor = request.user
    visit_file = get_object_or_404(VisitFile, pk=pk, doctor=doctor)
    visit_pk = visit_file.visit.pk
    visit_file.delete()
    messages.success(request, 'File deleted.')
    return redirect('visit_detail', pk=visit_pk)


@doctor_required
def search_patients(request):
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return render(request, 'patients/search_results.html', {'results': []})

    results = Patient.objects.filter(
        doctor=request.user,
        name__icontains=query
    ).values('id', 'name', 'phone', 'gender', 'date_of_birth')[:10]

    return render(request, 'patients/search_results.html', {'results': results})


@doctor_required
def pending_visits(request):
    return render(request, 'patients/pending_visits.html')
