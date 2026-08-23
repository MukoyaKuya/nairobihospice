from django.urls import path

from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.NotificationListView.as_view(), name='notification_list'),
    path('badge/', views.NotificationBadgeView.as_view(), name='unread_badge'),
    path('<uuid:pk>/read/', views.NotificationMarkReadView.as_view(), name='notification_read'),
    path('mark-all-read/', views.NotificationMarkAllReadView.as_view(), name='notification_mark_all_read'),
]
