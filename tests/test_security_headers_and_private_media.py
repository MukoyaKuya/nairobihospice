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


def test_csp_nonce_is_injected_and_script_unsafe_inline_is_absent(client):
    """Default application CSP header must use per-request script nonce without unsafe-inline in script-src."""
    response = client.get('/health/live/')
    assert response.status_code == 200
    csp = response['Content-Security-Policy']
    assert "nonce-" in csp
    # script-src should NOT contain 'unsafe-inline'
    script_part = [part for part in csp.split(';') if 'script-src' in part][0]
    assert "'unsafe-inline'" not in script_part


def test_csp_script_src_excludes_third_party_script_cdns(client):
    """script-src must not allow Tailwind CDN or unpkg after error pages were localized."""
    response = client.get('/health/live/')
    assert response.status_code == 200
    script_part = [part for part in response['Content-Security-Policy'].split(';') if 'script-src' in part][0]
    assert 'cdn.tailwindcss.com' not in script_part
    assert 'unpkg.com' not in script_part


def test_error_and_admin_templates_do_not_load_third_party_script_cdns():
    from django.conf import settings

    templates = [
        settings.BASE_DIR / 'templates' / '403.html',
        settings.BASE_DIR / 'templates' / '404.html',
        settings.BASE_DIR / 'templates' / '500.html',
        settings.BASE_DIR / 'templates' / 'admin' / 'login.html',
    ]
    for path in templates:
        text = path.read_text(encoding='utf-8')
        assert 'cdn.tailwindcss.com' not in text, path
        assert 'unpkg.com' not in text, path
        assert "{% static 'css/custom.css' %}" in text or '{% static "css/custom.css" %}' in text


def test_base_template_has_skip_to_content_link():
    from django.conf import settings

    text = (settings.BASE_DIR / 'templates' / 'base.html').read_text(encoding='utf-8')
    assert 'href="#main"' in text
    assert 'Skip to content' in text
    assert 'id="main"' in text
