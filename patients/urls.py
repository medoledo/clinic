from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('upcoming-visits/', views.upcoming_visits, name='upcoming_visits'),
    path('patients/', views.patient_list, name='patient_list'),
    path('patients/add/', views.add_patient, name='add_patient'),
    path('patients/<int:pk>/', views.patient_detail, name='patient_detail'),
    path('patients/<int:pk>/files/', views.patient_files, name='patient_files'),
    path('patients/<int:pk>/edit/', views.edit_patient, name='edit_patient'),
    path('patients/<int:pk>/delete/', views.delete_patient, name='delete_patient'),
    path('patients/<int:pk>/add-visit/', views.add_visit, name='add_visit'),
    path('visits/<int:pk>/', views.visit_detail, name='visit_detail'),
    path('visits/<int:pk>/edit/', views.edit_visit, name='edit_visit'),
    path('visits/<int:pk>/delete/', views.delete_visit, name='delete_visit'),
    path('visits/<int:pk>/print/', views.visit_print, name='visit_print'),
    path('visits/files/<int:pk>/delete/', views.delete_visit_file, name='delete_visit_file'),
    path('search-patients/', views.search_patients, name='search_patients'),
    path('transcribe-visit/', views.transcribe_and_parse, name='transcribe_visit'),
    path('transcribe-patient/', views.transcribe_patient_info, name='transcribe_patient'),
    path('check-suggestions/', views.check_suggestions, name='check_suggestions'),
    path('save-correction/', views.save_correction, name='save_correction'),
]
