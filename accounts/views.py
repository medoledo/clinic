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


@admin_required
def admin_dashboard(request):
    """
    Repurposed Admin Dashboard showing system-level activity, 
    logs, and navigation to the Django Admin.
    """
    from django.contrib.admin.models import LogEntry
    from django.db.models import Count
    
    # ── System Stats ──────────────────────────────────────────────────────────
    stats = {
        'total_users': User.objects.count(),
        'active_users': User.objects.filter(is_active=True).count(),
        'total_patients': Patient.objects.count(),
        'total_visits': Visit.objects.count(),
    }

    # ── Activity Logs — Detailed LogEntry ─────────────────────────────────────
    # This shows who did what in the system (via admin or app logic that logs)
    logs = (
        LogEntry.objects.all()
        .select_related('user', 'content_type')
        .order_by('-action_time')[:100]
    )

    # ── Recent System Content ─────────────────────────────────────────────────
    recent_patients = Patient.objects.order_by('-created_at')[:5]
    recent_visits = Visit.objects.select_related('patient', 'doctor').order_by('-created_at')[:5]

    context = {
        'stats': stats,
        'logs': logs,
        'recent_patients': recent_patients,
        'recent_visits': recent_visits,
    }
    return render(request, 'accounts/admin_dashboard.html', context)
