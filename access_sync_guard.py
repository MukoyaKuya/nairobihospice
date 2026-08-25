"""Fail-closed guard for local Microsoft Access import utilities.

These scripts must never run against production. Import this module from the
root-level sync_*.py helpers and call abort_if_production_access_sync() after
setdefault of DJANGO_SETTINGS_MODULE and before django.setup().
"""

from __future__ import annotations

import os

_ABORT_MESSAGE = (
    "SECURITY ERROR: Access sync scripts are strictly local migration utilities "
    "and must NEVER be executed against production environments."
)


def abort_if_production_access_sync(environ=None):
    """Raise RuntimeError when the process is configured for production.

    Aborts when DJANGO_SETTINGS_MODULE ends with ``.production`` or when
    DJANGO_DEBUG is an explicit false value (false/0/no). Django DEBUG=False
    in test settings is not consulted here so the unit test of this guard does
    not require a live production settings module.
    """
    env = os.environ if environ is None else environ
    settings_module = (env.get("DJANGO_SETTINGS_MODULE") or "").strip()
    debug_flag = (env.get("DJANGO_DEBUG") or "").strip().lower()
    if settings_module.endswith(".production") or debug_flag in ("false", "0", "no"):
        raise RuntimeError(_ABORT_MESSAGE)
