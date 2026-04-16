from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Count, Max, Min, Q
from django.utils import timezone
from datetime import timedelta

from .models import UserProfile, DoctorProfile
from .decorators import admin_required
from patients.models import Patient, Visit


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

        if not username or not password:
            messages.error(request, 'Username and password are required.')
            return render(request, 'accounts/login.html')

        try:
            temp_user = User.objects.get(username=username)
            if not temp_user.is_active and temp_user.check_password(password):
                messages.error(request, "Your account is currently inactive. Contact the administration.")
                return render(request, 'accounts/login.html')
        except User.DoesNotExist:
            pass

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
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


@require_POST
def logout_view(request):
    """Logout only via POST — prevents CSRF logout attacks via GET."""
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

    patients_qs = Patient.objects.all()
    visits_qs = Visit.objects.all()

    # ── Aggregate stats ───────────────────────────────────────────────────────
    patient_agg = patients_qs.aggregate(
        total=Count('id'),
        male=Count('id', filter=Q(gender='male')),
        female=Count('id', filter=Q(gender='female')),
    )
    total_patients = patient_agg['total']
    male_patients = patient_agg['male']
    female_patients = patient_agg['female']
    patients_with_visits = patients_qs.annotate(vc=Count('visits')).filter(vc__gt=0).count()
    patients_without_visits = total_patients - patients_with_visits

    total_visits = visits_qs.count()
    today_visits = visits_qs.filter(visit_date__date=today).count()
    this_week_visits = visits_qs.filter(visit_date__date__gte=this_week_start).count()
    this_month_visits = visits_qs.filter(visit_date__date__gte=this_month_start).count()
    last_month_visits = Visit.objects.filter(
        visit_date__date__gte=last_month_start,
        visit_date__date__lte=last_month_end,
    ).count()

    if last_month_visits > 0:
        visit_growth = round(((this_month_visits - last_month_visits) / last_month_visits) * 100, 1)
    else:
        visit_growth = 0
    abs_visit_growth = abs(visit_growth)

    oldest_row = visits_qs.aggregate(oldest=Min('visit_date'))
    oldest_date = oldest_row['oldest']
    if oldest_date and total_visits > 0:
        span_days = max(1, (today - oldest_date.date()).days + 1)
        avg_visits_per_day = round(total_visits / span_days, 1)
    else:
        avg_visits_per_day = 0

    visits_with_temp = visits_qs.filter(temperature__isnull=False).count()
    visits_with_bp = visits_qs.exclude(blood_pressure='').count()
    visits_with_pulse = visits_qs.filter(pulse__isnull=False).count()
    visits_with_weight = visits_qs.filter(weight__isnull=False).count()

    visits_with_files = visits_qs.annotate(fc=Count('files')).filter(fc__gt=0).count()
    visits_without_files = total_visits - visits_with_files

    recent_visits = (
        visits_qs
        .select_related('patient', 'doctor', 'doctor__doctor_profile')
        .prefetch_related('files')
        .order_by('-visit_date')[:15]
    )

    # ── Daily breakdown ───────────────────────────────────────────────────────
    from django.db.models.functions import TruncDate
    days_range = [today - timedelta(days=6 - i) for i in range(7)]
    daily_counts = {
        row['day']: row['cnt']
        for row in visits_qs
            .filter(visit_date__date__gte=days_range[0], visit_date__date__lte=today)
            .annotate(day=TruncDate('visit_date'))
            .values('day')
            .annotate(cnt=Count('id'))
    }
    daily_breakdown = [
        {'date': d, 'day_name': d.strftime('%A'), 'visits': daily_counts.get(d, 0)}
        for d in days_range
    ]

    context = {
        'total_patients': total_patients,
        'male_patients': male_patients,
        'female_patients': female_patients,
        'patients_with_visits': patients_with_visits,
        'patients_without_visits': patients_without_visits,
        'total_visits': total_visits,
        'today_visits': today_visits,
        'this_week_visits': this_week_visits,
        'this_month_visits': this_month_visits,
        'last_month_visits': last_month_visits,
        'visit_growth': visit_growth,
        'abs_visit_growth': abs_visit_growth,
        'avg_visits_per_day': avg_visits_per_day,
        'visits_with_temp': visits_with_temp,
        'visits_with_bp': visits_with_bp,
        'visits_with_pulse': visits_with_pulse,
        'visits_with_weight': visits_with_weight,
        'visits_with_files': visits_with_files,
        'visits_without_files': visits_without_files,
        'recent_visits': recent_visits,
        'daily_breakdown': daily_breakdown,
    }
    return render(request, 'accounts/admin_dashboard.html', context)
