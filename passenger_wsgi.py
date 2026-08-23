"""
WSGI config for HostPinnacle / cPanel Passenger Python deployments.
"""
import os
import sys

# Add project root and virtual environment path if needed
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CURRENT_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
