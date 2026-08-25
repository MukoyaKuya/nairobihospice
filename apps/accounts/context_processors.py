from .models import RoleChoices


def user_role_context(request):
    """
    Exposes role flags and choices in all templates.
    """
    if not request.user.is_authenticated:
        return {'is_authenticated': False}

    user = request.user
    role = user.role

    return {
        'current_user': user,
        'user_role': role,
        'user_role_display': getattr(user.profile, 'get_role_display', lambda: role)(),
        'is_doctor': user.is_doctor,
        'is_nurse': user.is_nurse,
        'is_clinical': user.is_clinical,
        'is_social_worker': user.is_social_worker,
        'is_counsellor': user.is_counsellor,
        'is_receptionist': user.is_receptionist,
        'is_pharmacist': user.is_pharmacist,
        'is_administrator': user.is_administrator,
        'is_manager': user.is_manager,
        'RoleChoices': RoleChoices,
        'csp_nonce': getattr(request, 'csp_nonce', ''),
    }
