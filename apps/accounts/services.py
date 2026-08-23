from django.db import transaction

from .models import RoleChoices, StaffProfile, User


@transaction.atomic
def create_staff_user(*, email, username, first_name, last_name, password, role=RoleChoices.NURSE, phone_number='', license_number='', department='Palliative Care Unit', qualifications='', is_staff=False, is_superuser=False):
    """
    Creates a User and corresponding StaffProfile inside an atomic transaction.
    """
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        phone_number=phone_number,
        is_staff=is_staff,
        is_superuser=is_superuser,
    )

    StaffProfile.objects.create(
        user=user,
        role=role,
        license_number=license_number,
        department=department,
        qualifications=qualifications,
    )
    return user


@transaction.atomic
def update_staff_profile(*, user: User, role=None, phone_number=None, license_number=None, department=None, qualifications=None, is_active_staff=None):
    if phone_number is not None:
        user.phone_number = phone_number
        user.save(update_fields=['phone_number'])

    profile = getattr(user, 'staff_profile', None)
    if profile:
        if role is not None:
            profile.role = role
        if license_number is not None:
            profile.license_number = license_number
        if department is not None:
            profile.department = department
        if qualifications is not None:
            profile.qualifications = qualifications
        if is_active_staff is not None:
            profile.is_active_staff = is_active_staff
        profile.save()
    return user
