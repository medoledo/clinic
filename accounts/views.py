from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.core.cache import cache
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

        # H7: IP-based rate limiting — max 5 failed attempts per 60 seconds
        ip = request.META.get('REMOTE_ADDR', 'unknown')
        rate_key = f'login_attempts_{ip}'
        attempts = cache.get(rate_key, 0)
        if attempts >= 5:
            messages.error(request, 'Too many failed login attempts. Please wait 60 seconds before trying again.')
            return render(request, 'accounts/login.html')

        # H5: Use authenticate() only — no pre-check that reveals if username exists
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if not user.is_active:
                # Inactive account — generic message; no enumeration risk here since
                # we only reach this after successful password verification internally
                messages.error(request, 'Your account is inactive. Contact administration.')
                cache.set(rate_key, attempts + 1, timeout=60)
                return render(request, 'accounts/login.html')
            cache.delete(rate_key)   # Reset counter on successful login
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
            cache.set(rate_key, attempts + 1, timeout=60)
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
