from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('sw.js', TemplateView.as_view(template_name='sw.js', content_type='application/javascript'), name='service_worker'),
    path('', lambda request: redirect('login'), name='home'),
    path('', include('accounts.urls')),
    path('', include('patients.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
