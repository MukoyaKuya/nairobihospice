from django.urls import path

from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.NotificationListView.as_view(), name='notification_list'),
    path('badge/', views.NotificationBadgeView.as_view(), name='unread_badge'),
    path('bulk-action/', views.NotificationBulkActionView.as_view(), name='notification_bulk_action'),
    path('mark-all-read/', views.NotificationMarkAllReadView.as_view(), name='notification_mark_all_read'),
    path('<uuid:pk>/read/', views.NotificationMarkReadView.as_view(), name='notification_read'),
    path('<uuid:pk>/delete/', views.NotificationDeleteView.as_view(), name='notification_delete'),
]
