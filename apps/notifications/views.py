from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import ListView, View

from .models import Notification


class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = 'notifications/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 30

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).order_by('-created_at')


class NotificationMarkReadView(LoginRequiredMixin, View):
    def post(self, request, pk):
        notif = get_object_or_404(Notification, pk=pk, recipient=request.user)
        notif.is_read = True
        notif.save()
        if notif.link_url:
            return redirect(notif.link_url)
        return redirect('notifications:notification_list')


class NotificationMarkAllReadView(LoginRequiredMixin, View):
    def post(self, request):
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return redirect('notifications:notification_list')


class NotificationBadgeView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            from django.http import HttpResponse
            return HttpResponse(status=204)
        from django.shortcuts import render
        unread_qs = Notification.objects.filter(recipient=request.user, is_read=False)
        return render(request, 'components/notification_badge.html', {
            'unread_notifications_count': unread_qs.count(),
            'recent_notifications': unread_qs.order_by('-created_at')[:5],
        })
