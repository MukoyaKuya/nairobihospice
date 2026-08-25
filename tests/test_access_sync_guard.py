import pytest

from access_sync_guard import abort_if_production_access_sync


def test_access_sync_guard_aborts_when_settings_module_is_production():
    with pytest.raises(RuntimeError, match="must NEVER be executed against production"):
        abort_if_production_access_sync({"DJANGO_SETTINGS_MODULE": "config.settings.production"})


def test_access_sync_guard_aborts_when_django_debug_is_false():
    with pytest.raises(RuntimeError, match="must NEVER be executed against production"):
        abort_if_production_access_sync({
            "DJANGO_SETTINGS_MODULE": "config.settings.development",
            "DJANGO_DEBUG": "false",
        })


def test_access_sync_guard_allows_explicit_development():
    abort_if_production_access_sync({
        "DJANGO_SETTINGS_MODULE": "config.settings.development",
        "DJANGO_DEBUG": "true",
    })


@pytest.mark.parametrize("script", [
    "sync_access_data.py",
    "sync_clinical_and_supply_data.py",
    "sync_complete_access_master.py",
])
def test_access_sync_scripts_call_shared_production_guard(script):
    from django.conf import settings

    text = (settings.BASE_DIR / script).read_text(encoding="utf-8")
    assert "abort_if_production_access_sync" in text
    assert "django.setup()" in text
    assert text.index("abort_if_production_access_sync") < text.index("django.setup()")
