from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Admin panel
    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-panel/manage-doctors/', views.manage_doctors, name='manage_doctors'),
    path('admin-panel/doctors/add/', views.add_doctor, name='add_doctor'),
    path('admin-panel/doctors/<int:pk>/edit/', views.edit_doctor, name='edit_doctor'),
    path('admin-panel/doctors/<int:pk>/reset-password/', views.reset_doctor_password, name='reset_doctor_password'),
    path('admin-panel/doctors/<int:pk>/toggle/', views.toggle_doctor_status, name='toggle_doctor_status'),
    path('admin-panel/doctors/<int:pk>/delete/', views.delete_doctor, name='delete_doctor'),
]
