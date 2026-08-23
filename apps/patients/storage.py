from django.conf import settings

from apps.documents.storage import PrivateFileSystemStorage

private_patient_photo_storage = PrivateFileSystemStorage(
    location=settings.PRIVATE_MEDIA_ROOT / 'patient_photos',
    base_url='',
)
