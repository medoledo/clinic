from functools import wraps
from django.shortcuts import redirect
from django.http import JsonResponse
from .models import UserProfile


def doctor_required(view_func):
    """Allow only authenticated, active doctors (users with role='doctor')."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        # Check is_active first to avoid an extra profile query for deactivated users
        if not request.user.is_active:
            from django.contrib.auth import logout
            logout(request)
            return redirect('login')
        try:
            profile = request.user.profile
            if profile.role == 'admin':
                return redirect('admin_dashboard')
            if profile.role != 'doctor':
                return redirect('login')
        except UserProfile.DoesNotExist:
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper


def admin_required(view_func):
    """Allow only authenticated admins (users with role='admin')."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        try:
            profile = request.user.profile
            if profile.role == 'doctor':
                return redirect('dashboard')
            if profile.role != 'admin':
                return redirect('login')
        except UserProfile.DoesNotExist:
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper


def post_required(view_func):
    """
    Require HTTP POST for state-mutating endpoints.
    Returns a 405 JSON response for non-POST requests.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.method != 'POST':
            return JsonResponse(
                {'success': False, 'message': 'Method not allowed.'},
                status=405,
            )
        return view_func(request, *args, **kwargs)
    return wrapper
