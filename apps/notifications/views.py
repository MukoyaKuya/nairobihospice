from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import ListView, View

from .models import Notification


class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = 'notifications/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 50

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).order_by('-created_at')


class NotificationMarkReadView(LoginRequiredMixin, View):
    def post(self, request, pk):
        notif = get_object_or_404(Notification, pk=pk, recipient=request.user)
        notif.is_read = True
        notif.save(update_fields=['is_read'])
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        if notif.link_url:
            return redirect(notif.link_url)
        return redirect('notifications:notification_list')


class NotificationMarkAllReadView(LoginRequiredMixin, View):
    def post(self, request):
        count = Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        messages.success(request, f"Marked {count} notifications as read.")
        return redirect('notifications:notification_list')


class NotificationDeleteView(LoginRequiredMixin, View):
    """Delete a single notification owned by the current user."""
    def post(self, request, pk):
        notif = get_object_or_404(Notification, pk=pk, recipient=request.user)
        notif.delete()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        messages.success(request, "Notification deleted.")
        return redirect('notifications:notification_list')


class NotificationBulkActionView(LoginRequiredMixin, View):
    """Handle bulk actions: delete selected, mark selected read/unread, or clear all."""
    def post(self, request):
        action = request.POST.get('action')
        selected_ids = request.POST.getlist('selected_ids')

        if action == 'delete_all':
            count, _ = Notification.objects.filter(recipient=request.user).delete()
            messages.success(request, f"Cleared all {count} notification(s).")
            return redirect('notifications:notification_list')

        if not selected_ids:
            messages.warning(request, "No notifications were selected.")
            return redirect('notifications:notification_list')

        user_notifs = Notification.objects.filter(recipient=request.user, pk__in=selected_ids)
        count = user_notifs.count()

        if action == 'delete':
            user_notifs.delete()
            messages.success(request, f"Deleted {count} notification(s).")
        elif action == 'mark_read':
            user_notifs.update(is_read=True)
            messages.success(request, f"Marked {count} notification(s) as read.")
        elif action == 'mark_unread':
            user_notifs.update(is_read=False)
            messages.success(request, f"Marked {count} notification(s) as unread.")

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
