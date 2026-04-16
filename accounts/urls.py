from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Admin panel
    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),
]
