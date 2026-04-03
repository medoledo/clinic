from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Count, Min, Q
from django.utils import timezone
from datetime import timedelta

from .models import UserProfile, DoctorProfile, AdminProfile
from .decorators import admin_required, post_required
from patients.models import Patient, Visit, VisitFile


# ─────────────────────────── Auth ────────────────────────────────────────────

def login_view(request):
    """Login page. Redirects authenticated users to their role's home."""
    if request.user.is_authenticated:
        try:
            role = request.user.profile.role
            if role == 'admin':
                return redirect('admin_dashboard')
            if role == 'doctor':
                return redirect('dashboard')
        except UserProfile.DoesNotExist:
            pass

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        remember_me = request.POST.get('remember_me')

        if not username or not password:
            messages.error(request, 'Username and password are required.')
            return render(request, 'accounts/login.html')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            if not user.is_active:
                messages.error(request, 'Your account has been deactivated. Contact admin.')
                return render(request, 'accounts/login.html')

            login(request, user)

            # Session expiry: 30 days if remember-me, else session-only
            request.session.set_expiry(60 * 60 * 24 * 30 if remember_me else 0)

            try:
                role = user.profile.role
                if role == 'admin':
                    return redirect('admin_dashboard')
                if role == 'doctor':
                    return redirect('dashboard')
            except UserProfile.DoesNotExist:
                pass

            messages.error(request, 'No role assigned to your account. Contact admin.')
            logout(request)
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'accounts/login.html')


def logout_view(request):
    """Logout must be POST to prevent CSRF logout via GET link."""
    if request.method == 'POST':
        logout(request)
    # Gracefully handle GET (e.g. direct URL bar navigation) for compatibility
    else:
        logout(request)
    return redirect('login')


# ─────────────────────────── Admin — Dashboard ───────────────────────────────

@admin_required
def admin_dashboard(request):
    today = timezone.now().date()
    this_week_start = today - timedelta(days=today.weekday())
    this_month_start = today.replace(day=1)
    last_month_end = this_month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    doctor_filter = request.GET.get('doctor_filter', '').strip()

    # Base querysets — filtered by selected doctor if provided
    doctors_qs = User.objects.filter(
        profile__role='doctor'
    ).select_related('profile', 'doctor_profile')

    patients_qs = Patient.objects.all()
    visits_qs = Visit.objects.all()

    doctor_filter_id = None
    if doctor_filter:
        # Validate it's a real doctor pk to avoid injection
        try:
            doctor_filter_id = int(doctor_filter)
            doctors_qs = doctors_qs.filter(pk=doctor_filter_id)
            patients_qs = patients_qs.filter(doctor_id=doctor_filter_id)
            visits_qs = visits_qs.filter(doctor_id=doctor_filter_id)
        except (ValueError, TypeError):
            doctor_filter = ''
            doctor_filter_id = None

    # ── Aggregate stats (single queries) ─────────────────────────────────────
    total_doctors = doctors_qs.count()
    active_doctors = doctors_qs.filter(is_active=True).count()
    inactive_doctors = total_doctors - active_doctors

    patient_agg = patients_qs.aggregate(
        total=Count('id'),
        male=Count('id', filter=Q(gender='male')),
        female=Count('id', filter=Q(gender='female')),
        with_visits=Count('id', filter=Q(visits__isnull=False)),
    )
    total_patients = patient_agg['total']
    active_patients = total_patients  # All patients are considered active since is_active field was removed
    inactive_patients = 0
    male_patients = patient_agg['male']
    female_patients = patient_agg['female']
    patients_with_visits = patients_qs.annotate(vc=Count('visits')).filter(vc__gt=0).count()
    patients_without_visits = total_patients - patients_with_visits

    # Blood type breakdown removed — field was deleted in migration 0003
    blood_types = {}

    # Visit stats
    total_visits = visits_qs.count()
    today_visits = visits_qs.filter(visit_date__date=today).count()
    this_week_visits = visits_qs.filter(visit_date__date__gte=this_week_start).count()
    this_month_visits = visits_qs.filter(visit_date__date__gte=this_month_start).count()

    # Last month visits (must re-apply doctor filter if set)
    lm_filter = Q(visit_date__date__gte=last_month_start, visit_date__date__lte=last_month_end)
    if doctor_filter:
        lm_filter &= Q(doctor_id=int(doctor_filter))
    last_month_visits = Visit.objects.filter(lm_filter).count()

    if last_month_visits > 0:
        visit_growth = round(((this_month_visits - last_month_visits) / last_month_visits) * 100, 1)
    else:
        visit_growth = 0
    abs_visit_growth = abs(visit_growth)

    # Average visits per day — use Min aggregation instead of order_by().first()
    oldest_date_row = visits_qs.aggregate(oldest=Min('visit_date'))
    oldest_date = oldest_date_row['oldest']
    if oldest_date and total_visits > 0:
        span_days = max(1, (today - oldest_date.date()).days + 1)
        avg_visits_per_day = round(total_visits / span_days, 1)
    else:
        avg_visits_per_day = 0

    avg_visits_per_doctor = round(total_visits / max(1, total_doctors), 1)
    avg_visits_per_patient = round(total_visits / max(1, total_patients), 1)
    avg_patients_per_doctor = round(total_patients / max(1, total_doctors), 1)

    visits_with_files = visits_qs.annotate(fc=Count('files')).filter(fc__gt=0).count()
    visits_without_files = total_visits - visits_with_files

    # Vitals coverage
    visits_with_temp = visits_qs.filter(temperature__isnull=False).count()
    visits_with_bp = visits_qs.exclude(blood_pressure='').count()
    visits_with_pulse = visits_qs.filter(pulse__isnull=False).count()
    visits_with_weight = visits_qs.filter(weight__isnull=False).count()

    # ── Doctors leaderboard — ONE query with annotations ─────────────────────
    # Annotate all stats in a single DB round-trip instead of a per-doctor loop
    doctors_annotated = doctors_qs.annotate(
        patient_count=Count('patients', distinct=True),
        visit_count=Count('visits', distinct=True),
        today_count=Count(
            'visits',
            filter=Q(visits__visit_date__date=today),
            distinct=True,
        ),
        month_count=Count(
            'visits',
            filter=Q(visits__visit_date__date__gte=this_month_start),
            distinct=True,
        ),
    ).order_by('-visit_count')

    doctors_data = []
    for doc in doctors_annotated:
        try:
            full_name = doc.doctor_profile.full_name
        except DoctorProfile.DoesNotExist:
            full_name = doc.username

        # last_active requires one extra query per doctor — acceptable at dashboard level
        # (only shows top doctors, not millions of rows)
        last_visit = Visit.objects.filter(doctor=doc).only('visit_date').order_by('-visit_date').first()
        doctors_data.append({
            'user': doc,
            'profile': doc.profile,
            'full_name': full_name,
            'patient_count': doc.patient_count,
            'visit_count': doc.visit_count,
            'today_visits': doc.today_count,
            'month_visits': doc.month_count,
            'last_active': last_visit.visit_date if last_visit else None,
        })

    # ── Most-visited patients — annotated, no extra per-patient queries ───────
    most_visited = (
        patients_qs
        .annotate(vc=Count('visits'))
        .filter(vc__gt=0)
        .order_by('-vc')[:10]
    )
    most_visited_data = []
    for p in most_visited:
        last_v = Visit.objects.select_related('doctor__doctor_profile').filter(patient=p).order_by('-visit_date').first()
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

    no_visit_patients = (
        patients_qs.annotate(vc=Count('visits')).filter(vc=0)
        .select_related('doctor')[:10]
    )

    recent_visits = (
        visits_qs
        .select_related('patient', 'doctor', 'doctor__doctor_profile')
        .prefetch_related('files')
        .order_by('-visit_date')[:15]
    )

    # ── Daily breakdown for last 7 days — 7 queries (bounded, not N×rows) ─────
    daily_breakdown = []
    for i in range(7):
        d = today - timedelta(days=6 - i)
        day_visits = visits_qs.filter(visit_date__date=d).count()
        daily_breakdown.append({
            'date': d,
            'day_name': d.strftime('%A'),
            'visits': day_visits,
        })

    # Weekday analysis
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    weekday_data = []
    for i, name in enumerate(day_names):
        django_day = i + 2 if i < 6 else 1
        wd_visits = visits_qs.filter(visit_date__week_day=django_day).count()
        weekday_data.append({'name': name, 'visits': wd_visits})
    weekday_data.sort(key=lambda x: x['visits'], reverse=True)
    busiest_day = weekday_data[0]['name'] if weekday_data else '—'

    context = {
        'doctor_filter': doctor_filter,
        'doctor_filter_id': doctor_filter_id,
        'all_doctors': User.objects.filter(profile__role='doctor').select_related('profile', 'doctor_profile'),
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


# ─────────────────────────── Admin — Manage Doctors ──────────────────────────

@admin_required
def manage_doctors(request):
    today = timezone.now().date()
    this_month_start = today.replace(day=1)

    # Single DB query: all doctors with all counts annotated — no per-doctor loop
    doctors_qs = (
        User.objects
        .filter(profile__role='doctor')
        .select_related('profile', 'doctor_profile')
        .annotate(
            patient_count=Count('patients', distinct=True),
            visit_count=Count('visits', distinct=True),
            today_count=Count(
                'visits',
                filter=Q(visits__visit_date__date=today),
                distinct=True,
            ),
            month_count=Count(
                'visits',
                filter=Q(visits__visit_date__date__gte=this_month_start),
                distinct=True,
            ),
        )
        .order_by('-visit_count')
    )

    doctors_data = []
    for doc in doctors_qs:
        try:
            full_name = doc.doctor_profile.full_name
            spec = doc.doctor_profile.specialization
            phone = doc.doctor_profile.phone
        except DoctorProfile.DoesNotExist:
            full_name = doc.username
            spec = ''
            phone = ''

        last_visit = (
            Visit.objects.filter(doctor=doc)
            .only('visit_date')
            .order_by('-visit_date')
            .first()
        )
        doctors_data.append({
            'user': doc,
            'full_name': full_name,
            'specialization': spec,
            'phone': phone,
            'patient_count': doc.patient_count,
            'visit_count': doc.visit_count,
            'today_visits': doc.today_count,
            'month_visits': doc.month_count,
            'last_active': last_visit.visit_date if last_visit else None,
        })

    context = {
        'doctors_data': doctors_data,
        'total_doctors': len(doctors_data),
        'active_doctors': sum(1 for d in doctors_data if d['user'].is_active),
        'total_patients': Patient.objects.count(),
        'total_visits': Visit.objects.count(),
    }
    return render(request, 'accounts/manage_doctors.html', context)


# ─────────────────────────── Admin — Doctor CRUD ──────────────────────────────

@admin_required
def add_doctor(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()[:150]
        password = request.POST.get('password', '').strip()
        full_name = request.POST.get('full_name', '').strip()[:200]
        specialization = request.POST.get('specialization', '').strip()[:200]
        phone = request.POST.get('phone', '').strip()[:20]
        is_active = request.POST.get('is_active') == 'on'

        if not username:
            return JsonResponse({'success': False, 'message': 'Username is required.'})
        if not password or len(password) < 8:
            return JsonResponse({'success': False, 'message': 'Password must be at least 8 characters.'})
        if not full_name:
            return JsonResponse({'success': False, 'message': 'Full name is required.'})
        if User.objects.filter(username=username).exists():
            return JsonResponse({'success': False, 'message': 'Username already taken.'})

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
        return JsonResponse({'success': True, 'message': f'Doctor "{full_name}" added successfully.'})

    return render(request, 'accounts/doctor_form.html', {'action': 'Add'})


@admin_required
def edit_doctor(request, pk):
    doctor_user = get_object_or_404(User, pk=pk, profile__role='doctor')
    try:
        profile = doctor_user.doctor_profile
    except DoctorProfile.DoesNotExist:
        profile = None

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()[:200]
        username = request.POST.get('username', '').strip()[:150]
        specialization = request.POST.get('specialization', '').strip()[:200]
        phone = request.POST.get('phone', '').strip()[:20]
        is_active = request.POST.get('is_active') == 'on'

        if not full_name:
            return JsonResponse({'success': False, 'message': 'Full name is required.'})

        if username and username != doctor_user.username:
            if User.objects.filter(username=username).exclude(pk=pk).exists():
                return JsonResponse({'success': False, 'message': 'Username already taken.'})
            doctor_user.username = username

        if profile:
            profile.full_name = full_name
            profile.specialization = specialization
            profile.phone = phone
            profile.save()

        doctor_user.is_active = is_active
        doctor_user.save()
        return JsonResponse({'success': True, 'message': f'Doctor "{full_name}" updated successfully.'})

    context = {
        'action': 'Edit',
        'doctor_user': doctor_user,
        'profile': profile,
    }
    return render(request, 'accounts/doctor_form.html', context)


@admin_required
def reset_doctor_password(request, pk):
    doctor_user = get_object_or_404(User, pk=pk, profile__role='doctor')
    try:
        full_name = doctor_user.doctor_profile.full_name
    except DoctorProfile.DoesNotExist:
        full_name = doctor_user.username

    if request.method == 'POST':
        new_password = request.POST.get('new_password', '').strip()
        if not new_password or len(new_password) < 8:
            return JsonResponse({'success': False, 'message': 'Password must be at least 8 characters.'})
        doctor_user.set_password(new_password)
        doctor_user.save()
        return JsonResponse({'success': True, 'message': f'Password for "{full_name}" reset successfully.'})

    return render(request, 'accounts/reset_password.html', {'doctor_user': doctor_user})


@admin_required
@post_required
def toggle_doctor_status(request, pk):
    """Toggle doctor active status — POST only to prevent CSRF via GET."""
    doctor_user = get_object_or_404(User, pk=pk, profile__role='doctor')
    doctor_user.is_active = not doctor_user.is_active
    doctor_user.save(update_fields=['is_active'])
    status = 'activated' if doctor_user.is_active else 'deactivated'
    try:
        full_name = doctor_user.doctor_profile.full_name
    except DoctorProfile.DoesNotExist:
        full_name = doctor_user.username
    return JsonResponse({'success': True, 'message': f'Doctor "{full_name}" {status}.'})


@admin_required
def delete_doctor(request, pk):
    doctor_user = get_object_or_404(User, pk=pk, profile__role='doctor')
    patient_count = Patient.objects.filter(doctor=doctor_user).count()

    if patient_count > 0:
        return JsonResponse({
            'success': False,
            'message': f'Cannot delete \u2014 this doctor has {patient_count} patient(s). Deactivate them instead.',
        })

    if request.method == 'POST':
        try:
            full_name = doctor_user.doctor_profile.full_name
        except DoctorProfile.DoesNotExist:
            full_name = doctor_user.username
        doctor_user.delete()
        return JsonResponse({'success': True, 'message': f'Doctor "{full_name}" deleted successfully.'})

    return render(request, 'accounts/confirm_delete.html', {'doctor_user': doctor_user})
