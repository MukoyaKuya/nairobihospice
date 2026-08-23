from .models import Notification


def unread_notifications_processor(request):
    if not request.user.is_authenticated:
        return {'unread_notifications_count': 0, 'recent_notifications': []}

    unread_qs = Notification.objects.filter(recipient=request.user, is_read=False)
    return {
        'unread_notifications_count': unread_qs.count(),
        'recent_notifications': unread_qs.order_by('-created_at')[:5],
    }
