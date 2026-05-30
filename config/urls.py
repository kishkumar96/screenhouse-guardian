from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.views.generic import TemplateView


def health_check(request):
    return JsonResponse({'status': 'ok'})


urlpatterns = [
    path('', TemplateView.as_view(template_name='home.html'), name='home'),
    path('health/', health_check, name='health_check'),
    path('admin/', admin.site.urls),
    # Top-level observe routes — URL must match what QR codes encode:
    #   /observe/<unit_code>/          observation form
    #   /observe/<unit_code>/timeline/ observation history
    path('observe/', include('monitoring.observe_urls')),
    path('inventory/', include('inventory.urls', namespace='inventory')),
    path('monitoring/', include('monitoring.urls', namespace='monitoring')),
    path('qr/', include('qr.urls', namespace='qr')),
    path('dashboard/', include('dashboard.urls', namespace='dashboard')),
    path('exports/', include('exports.urls', namespace='exports')),
]

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
