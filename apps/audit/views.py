from django.views.generic import ListView

from apps.accounts.permissions import ManagerRequiredMixin

from .models import AuditEvent


class AuditLogListView(ManagerRequiredMixin, ListView):
    model = AuditEvent
    template_name = 'audit/audit_list.html'
    context_object_name = 'events'
    paginate_by = 50

    def get_queryset(self):
        qs = AuditEvent.objects.all().select_related('user').order_by('-timestamp')
        action = self.request.GET.get('action')
        resource = self.request.GET.get('resource_type')
        search = self.request.GET.get('q')

        if action:
            qs = qs.filter(action=action)
        if resource:
            qs = qs.filter(resource_type__icontains=resource)
        if search:
            qs = qs.filter(summary__icontains=search)
        return qs
