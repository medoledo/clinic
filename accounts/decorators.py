from functools import wraps
from django.shortcuts import redirect


def doctor_required(view_func):
    """Allow only authenticated doctors (users with doctor_profile)."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if hasattr(request.user, 'admin_profile'):
            return redirect('admin_dashboard')
        if not hasattr(request.user, 'doctor_profile'):
            return redirect('login')
        if not request.user.is_active:
            from django.contrib.auth import logout
            logout(request)
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper


def admin_required(view_func):
    """Allow only authenticated admins (users with admin_profile)."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if hasattr(request.user, 'doctor_profile'):
            return redirect('dashboard')
        if not hasattr(request.user, 'admin_profile'):
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper
