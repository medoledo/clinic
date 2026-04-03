from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Count
from django.utils import timezone

from .models import DoctorProfile, AdminProfile
from .decorators import admin_required
from patients.models import Patient, Visit


def login_view(request):
    if request.user.is_authenticated:
        if hasattr(request.user, 'admin_profile'):
            return redirect('admin_dashboard')
        if hasattr(request.user, 'doctor_profile'):
            return redirect('dashboard')

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
                request.session.set_expiry(60 * 60 * 24 * 30)  # 30 days
            else:
                request.session.set_expiry(0)  # expires on browser close

            if hasattr(user, 'admin_profile'):
                return redirect('admin_dashboard')
            elif hasattr(user, 'doctor_profile'):
                return redirect('dashboard')
            else:
                messages.error(request, 'Invalid username or password.')
                logout(request)
                return render(request, 'accounts/login.html')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'accounts/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


@admin_required
def admin_dashboard(request):
    doctors = User.objects.filter(doctor_profile__isnull=False).select_related('doctor_profile')
    doctors_data = []
    for doc in doctors:
        patient_count = Patient.objects.filter(doctor=doc).count()
        visit_count = Visit.objects.filter(doctor=doc).count()
        last_visit = Visit.objects.filter(doctor=doc).order_by('-visit_date').first()
        doctors_data.append({
            'user': doc,
            'profile': doc.doctor_profile,
            'patient_count': patient_count,
            'visit_count': visit_count,
            'last_active': last_visit.visit_date if last_visit else None,
        })

    total_patients = Patient.objects.count()
    total_visits = Visit.objects.count()
    total_doctors = doctors.count()
    active_doctors = doctors.filter(is_active=True).count()

    context = {
        'doctors_data': doctors_data,
        'total_doctors': total_doctors,
        'active_doctors': active_doctors,
        'total_patients': total_patients,
        'total_visits': total_visits,
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
        DoctorProfile.objects.create(
            user=user,
            full_name=full_name,
            specialization=specialization,
            phone=phone,
        )
        messages.success(request, f'Doctor "{full_name}" added successfully.')
        return redirect('admin_dashboard')

    return render(request, 'accounts/doctor_form.html', {'action': 'Add'})


@admin_required
def edit_doctor(request, pk):
    doctor_user = get_object_or_404(User, pk=pk, doctor_profile__isnull=False)
    profile = doctor_user.doctor_profile

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        specialization = request.POST.get('specialization', '').strip()
        phone = request.POST.get('phone', '').strip()
        is_active = request.POST.get('is_active') == 'on'

        profile.full_name = full_name
        profile.specialization = specialization
        profile.phone = phone
        profile.save()

        doctor_user.is_active = is_active
        doctor_user.save()

        messages.success(request, f'Doctor "{full_name}" updated successfully.')
        return redirect('admin_dashboard')

    context = {
        'action': 'Edit',
        'doctor_user': doctor_user,
        'profile': profile,
    }
    return render(request, 'accounts/doctor_form.html', context)


@admin_required
def reset_doctor_password(request, pk):
    doctor_user = get_object_or_404(User, pk=pk, doctor_profile__isnull=False)

    if request.method == 'POST':
        new_password = request.POST.get('new_password', '').strip()
        if new_password:
            doctor_user.set_password(new_password)
            doctor_user.save()
            messages.success(request, f'Password for "{doctor_user.doctor_profile.full_name}" reset successfully.')
        else:
            messages.error(request, 'Password cannot be empty.')
        return redirect('admin_dashboard')

    return render(request, 'accounts/reset_password.html', {'doctor_user': doctor_user})


@admin_required
def toggle_doctor_status(request, pk):
    doctor_user = get_object_or_404(User, pk=pk, doctor_profile__isnull=False)
    doctor_user.is_active = not doctor_user.is_active
    doctor_user.save()
    status = 'activated' if doctor_user.is_active else 'deactivated'
    messages.success(request, f'Doctor "{doctor_user.doctor_profile.full_name}" {status}.')
    return redirect('admin_dashboard')


@admin_required
def delete_doctor(request, pk):
    doctor_user = get_object_or_404(User, pk=pk, doctor_profile__isnull=False)
    patient_count = Patient.objects.filter(doctor=doctor_user).count()

    if patient_count > 0:
        messages.error(
            request,
            f'Cannot delete doctor — they have {patient_count} patient(s). Deactivate them instead.'
        )
        return redirect('admin_dashboard')

    if request.method == 'POST':
        name = doctor_user.doctor_profile.full_name
        doctor_user.delete()
        messages.success(request, f'Doctor "{name}" deleted successfully.')
        return redirect('admin_dashboard')

    return render(request, 'accounts/confirm_delete.html', {'doctor_user': doctor_user})
