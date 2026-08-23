from pathlib import Path

import pytest
from django.test import override_settings


@pytest.mark.django_db
def test_private_media_is_not_served_by_urlpatterns(client, settings):
    settings.DEBUG = False
    response = client.get('/media/clinical_documents/example.pdf')
    assert response.status_code == 404


@override_settings(
    CONTENT_SECURITY_POLICY="default-src 'self'; object-src 'none'",
    SECURE_CONTENT_TYPE_NOSNIFF=True,
    X_FRAME_OPTIONS='DENY',
)
def test_security_headers_are_present(client):
    response = client.get('/health/live/')
    assert response.status_code == 200
    assert response['X-Content-Type-Options'] == 'nosniff'
    assert response['X-Frame-Options'] == 'DENY'
    assert response['Content-Security-Policy'] == "default-src 'self'; object-src 'none'"


def test_private_storage_has_no_public_base_url(settings):
    from apps.documents.storage import private_document_storage
    from apps.patients.storage import private_patient_photo_storage

    with pytest.raises(ValueError):
        private_document_storage.url('example.pdf')
    with pytest.raises(ValueError):
        private_patient_photo_storage.url('example.jpg')
    assert Path(settings.PRIVATE_MEDIA_ROOT).name == 'private_media'
