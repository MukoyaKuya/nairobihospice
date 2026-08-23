"""
URL configuration for Nairobi Hospice Palliative Care Management System.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import include, path
from django.views import defaults as default_views
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from apps.reporting.views import IndexRedirectView

from . import health

admin.site.site_header = "Nairobi Hospice PCMS Administration"
admin.site.site_title = "Nairobi Hospice PCMS Admin"
admin.site.index_title = "System Management & Database Console"

handler404 = 'django.views.defaults.page_not_found'
handler500 = 'django.views.defaults.server_error'
handler403 = 'django.views.defaults.permission_denied'
handler400 = 'django.views.defaults.bad_request'

urlpatterns = [
    path('', IndexRedirectView.as_view(), name='index'),
    path('health/live/', health.live, name='health_live'),
    path('health/ready/', health.ready, name='health_ready'),
    path('office/', admin.site.urls),

    # Core Domain Apps
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('patients/', include('apps.patients.urls', namespace='patients')),
    path('referrals/', include('apps.referrals.urls', namespace='referrals')),
    path('care/', include('apps.care.urls', namespace='care')),
    path('encounters/', include('apps.encounters.urls', namespace='encounters')),
    path('assessments/', include('apps.assessments.urls', namespace='assessments')),
    path('symptoms/', include('apps.symptoms.urls', namespace='symptoms')),
    path('medications/', include('apps.medications.urls', namespace='medications')),
    path('appointments/', include('apps.appointments.urls', namespace='appointments')),
    path('documents/', include('apps.documents.urls', namespace='documents')),
    path('communications/', include('apps.communications.urls', namespace='communications')),
    path('notifications/', include('apps.notifications.urls', namespace='notifications')),
    path('reporting/', include('apps.reporting.urls', namespace='reporting')),
    path('operations/', include('apps.operations.urls', namespace='operations')),
    path('audit/', include('apps.audit.urls', namespace='audit')),

    # REST API v1
    path('api/v1/', include('api.v1.urls', namespace='api_v1')),
    path('api/schema/', staff_member_required(SpectacularAPIView.as_view()), name='schema'),
    path('api/docs/', staff_member_required(SpectacularSwaggerView.as_view(url_name='schema')), name='swagger-ui'),
    path('api/redoc/', staff_member_required(SpectacularRedocView.as_view(url_name='schema')), name='redoc'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += [
        path('404/', default_views.page_not_found, kwargs={'exception': Exception('Page not found')}),
        path('403/', default_views.permission_denied, kwargs={'exception': Exception('Permission denied')}),
        path('500/', default_views.server_error),
        path('400/', default_views.bad_request, kwargs={'exception': Exception('Bad request')}),
    ]
