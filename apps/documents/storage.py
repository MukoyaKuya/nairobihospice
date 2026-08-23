from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateFileSystemStorage(FileSystemStorage):
    """Filesystem storage that cannot generate a public URL."""

    def url(self, name):
        raise ValueError('Private files must be delivered through an authorized view.')

private_document_storage = PrivateFileSystemStorage(
    location=settings.PRIVATE_MEDIA_ROOT / 'clinical_documents',
    # An empty base URL prevents Django from inheriting MEDIA_URL and
    # accidentally exposing this storage through a public media route.
    base_url='/',
)
