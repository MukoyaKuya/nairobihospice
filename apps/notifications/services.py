from typing import Iterable, List, Optional

from django.urls import reverse

from apps.accounts.models import RoleChoices, StaffProfile, User

from .models import Notification, NotificationTypeChoices
from .webhooks import dispatch_webhook_event


def send_notification(
    *,
    recipient: User,
    notification_type: NotificationTypeChoices,
    title: str,
    message: str,
    link_url: str = ''
) -> Notification:
    """
    Creates an individual notification record for a recipient user.
    """
    return Notification.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        title=title,
        message=message,
        link_url=link_url,
    )


def notify_role_group(
    *,
    roles: Iterable[RoleChoices],
    notification_type: NotificationTypeChoices,
    title: str,
    message: str,
    link_url: str = '',
    exclude_user: Optional[User] = None,
) -> List[Notification]:
    """
    Broadcasts a notification to all active staff members holding specific clinical/operational roles.
    """
    staff_qs = StaffProfile.objects.filter(
        role__in=roles,
        is_active_staff=True,
        user__is_active=True,
    ).select_related('user')

    if exclude_user:
        staff_qs = staff_qs.exclude(user=exclude_user)

    notifications = []
    for staff in staff_qs:
        notifications.append(
            Notification(
                recipient=staff.user,
                notification_type=notification_type,
                title=title,
                message=message,
                link_url=link_url,
            )
        )

    if notifications:
        Notification.objects.bulk_create(notifications)

    return notifications


def notify_clinical_team_of_new_patient(*, patient, registered_by: Optional[User] = None) -> List[Notification]:
    """
    Triggered when a receptionist (or staff member) registers a new patient.
    Alerts active Doctors, Nurses, and Clinical Officers so they can begin triage / intake assessment.
    Also dispatches the external webhook event 'patient.registered'.
    """
    title = f"New Patient Registered: {patient.full_name} ({patient.hospice_number})"
    by = f" Registered by {registered_by.display_name}." if registered_by else ""

    message = (
        f"A new palliative patient was registered into the system.{by} "
        f"Ready for triage, clinical intake assessment, and care plan development."
    )

    try:
        link_url = reverse('patients:patient_detail', kwargs={'pk': patient.pk})
    except Exception:
        link_url = f"/patients/{patient.pk}/"

    clinical_roles = [
        RoleChoices.DOCTOR,
        RoleChoices.NURSE,
        RoleChoices.CLINICAL_OFFICER,
    ]

    notifs = notify_role_group(
        roles=clinical_roles,
        notification_type=NotificationTypeChoices.NEW_PATIENT_REGISTERED,
        title=title,
        message=message,
        link_url=link_url,
        exclude_user=registered_by,
    )

    # Dispatch outbound webhook payload
    dispatch_webhook_event(
        event_name='patient.registered',
        payload={
            'patient_id': str(patient.id),
            'hospice_number': patient.hospice_number,
            'registration_date': patient.registration_date.isoformat() if patient.registration_date else None,
        }
    )

    return notifs


def notify_staff_of_new_appointment(*, appointment, scheduled_by: Optional[User] = None) -> List[Notification]:
    """
    Triggered when a receptionist (or staff member) schedules a new clinic or home visit.
    Alerts the assigned staff member (doctor/nurse) and dispatches the 'appointment.scheduled' webhook.
    """
    title = f"New Appointment: {appointment.patient.full_name} - {appointment.get_appointment_type_display()}"
    date_str = appointment.scheduled_date.strftime('%d %b %Y')
    time_str = appointment.scheduled_time.strftime('%H:%M') if hasattr(appointment.scheduled_time, 'strftime') else str(appointment.scheduled_time)
    loc_str = f" @ {appointment.location}" if appointment.location else ""
    reason_str = f" Reason: {appointment.reason}" if appointment.reason else ""

    message = (
        f"Scheduled for {date_str} at {time_str}{loc_str}.{reason_str} "
        f"Assigned to {appointment.staff_member.user.display_name}."
    )

    try:
        link_url = reverse('appointments:appointment_list')
    except Exception:
        link_url = '/appointments/'

    notifs = []

    # 1. Notify assigned staff member
    if appointment.staff_member and appointment.staff_member.user:
        assigned_user = appointment.staff_member.user
        if scheduled_by is None or assigned_user != scheduled_by:
            notif = send_notification(
                recipient=assigned_user,
                notification_type=NotificationTypeChoices.NEW_APPOINTMENT_SCHEDULED,
                title=title,
                message=message,
                link_url=link_url,
            )
            notifs.append(notif)

    # 2. Also notify clinical leads (Doctors / Head Nurses) if scheduled by reception and not assigned to them
    clinical_roles = [RoleChoices.DOCTOR, RoleChoices.NURSE]
    other_notifs = notify_role_group(
        roles=clinical_roles,
        notification_type=NotificationTypeChoices.NEW_APPOINTMENT_SCHEDULED,
        title=title,
        message=message,
        link_url=link_url,
        exclude_user=appointment.staff_member.user if appointment.staff_member else scheduled_by,
    )
    notifs.extend(other_notifs)

    # Dispatch outbound webhook payload
    dispatch_webhook_event(
        event_name='appointment.scheduled',
        payload={
            'appointment_id': str(appointment.id),
            'patient_id': str(appointment.patient.id),
            'hospice_number': appointment.patient.hospice_number,
            'appointment_type': appointment.appointment_type,
            'scheduled_date': appointment.scheduled_date.isoformat(),
            'scheduled_time': str(appointment.scheduled_time),
        }
    )

    return notifs


def notify_operations_of_deletion_request(*, deletion_req, request_type: str = 'patient') -> List[Notification]:
    """
    Triggered when front desk or clinical staff submit a deletion request.
    Alerts Operations Managers and Administrators, and dispatches 'deletion_request.created' webhook.
    """
    if request_type == 'patient':
        title = f"Patient Deletion Requested: {deletion_req.patient_name} ({deletion_req.hospice_number})"
        item_desc = f"patient file {deletion_req.patient_name} ({deletion_req.hospice_number})"
    else:
        title = f"Appointment Deletion Requested: {deletion_req.patient_name}"
        item_desc = f"appointment for {deletion_req.patient_name} on {deletion_req.scheduled_date}"

    requester_name = deletion_req.requested_by.display_name if deletion_req.requested_by else "Staff"
    message = (
        f"{requester_name} submitted a deletion request for {item_desc}. "
        f"Reason: {deletion_req.reason}. Review and approval required."
    )
    try:
        link_url = reverse('operations:deletion_requests')
    except Exception:
        link_url = '/operations/deletions/'

    manager_roles = [RoleChoices.MANAGER, RoleChoices.ADMINISTRATOR]
    notifs = notify_role_group(
        roles=manager_roles,
        notification_type=NotificationTypeChoices.DELETION_REQUEST_CREATED,
        title=title,
        message=message,
        link_url=link_url,
        exclude_user=deletion_req.requested_by,
    )

    # Dispatch outbound webhook
    dispatch_webhook_event(
        event_name='deletion_request.created',
        payload={
            'request_id': str(deletion_req.id),
            'request_type': request_type,
            'patient_name': deletion_req.patient_name,
            'hospice_number': getattr(deletion_req, 'hospice_number', ''),
            'reason': deletion_req.reason,
            'requested_by': deletion_req.requested_by.email if deletion_req.requested_by else None,
        }
    )

    return notifs


def notify_requester_of_deletion_resolution(*, deletion_req, approved: bool, request_type: str = 'patient') -> Optional[Notification]:
    """
    Triggered when Operations Manager approves or rejects a deletion request.
    Alerts the requesting staff member (e.g. receptionist) and dispatches webhook.
    """
    if not deletion_req.requested_by:
        return None

    notif_type = NotificationTypeChoices.DELETION_REQUEST_APPROVED if approved else NotificationTypeChoices.DELETION_REQUEST_REJECTED

    if request_type == 'patient':
        item_desc = f"patient record for {deletion_req.patient_name} ({deletion_req.hospice_number})"
    else:
        item_desc = f"appointment record for {deletion_req.patient_name}"

    if approved:
        title = f"Deletion Request Approved: {deletion_req.patient_name}"
        notes_str = f" Reviewer notes: {deletion_req.review_notes}" if deletion_req.review_notes else ""
        message = f"Your deletion request for {item_desc} has been approved by Operations Management and permanently removed from the system.{notes_str}"
    else:
        title = f"Deletion Request Rejected: {deletion_req.patient_name}"
        notes_str = f" Reason / Notes: {deletion_req.review_notes}" if deletion_req.review_notes else ""
        message = f"Your deletion request for {item_desc} was reviewed and rejected by Operations Management.{notes_str}"

    try:
        link_url = reverse('patients:patient_list') if request_type == 'patient' else reverse('appointments:appointment_list')
    except Exception:
        link_url = '/patients/' if request_type == 'patient' else '/appointments/'

    notif = send_notification(
        recipient=deletion_req.requested_by,
        notification_type=notif_type,
        title=title,
        message=message,
        link_url=link_url,
    )

    event_suffix = 'approved' if approved else 'rejected'
    dispatch_webhook_event(
        event_name=f'deletion_request.{event_suffix}',
        payload={
            'request_id': str(deletion_req.id),
            'request_type': request_type,
            'patient_name': deletion_req.patient_name,
            'hospice_number': getattr(deletion_req, 'hospice_number', ''),
            'status': deletion_req.status,
            'reviewed_by': deletion_req.reviewed_by.email if deletion_req.reviewed_by else None,
            'review_notes': deletion_req.review_notes,
        }
    )

    return notif

