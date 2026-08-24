import os

from django.core.wsgi import get_wsgi_application

# Default to production: it fail-fasts on missing required environment
# configuration, so a misconfigured deployment is loud instead of insecure.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')

application = get_wsgi_application()
