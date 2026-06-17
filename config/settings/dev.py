"""
Development settings for Inveterate project.
"""
import os

from .base import *

# Override for development
DEBUG = True

ALLOWED_HOSTS = ['*']

# Cookie domain. Leave unset for localhost (the default). If your console and
# Proxmox live on sibling subdomains, set COOKIE_DOMAIN (e.g. ".example.com")
# so the PVEAuthCookie can reach Proxmox.
SESSION_COOKIE_DOMAIN = os.environ.get('COOKIE_DOMAIN') or None
CSRF_COOKIE_DOMAIN = os.environ.get('COOKIE_DOMAIN') or None

# Development-specific apps (optional, only if installed)
try:
    import django_extensions  # noqa: F401
    INSTALLED_APPS += ['django_extensions']
except ImportError:
    pass

# Simplified logging for development — console only, no file handler
LOGGING['root']['level'] = 'DEBUG'
LOGGING['root']['handlers'] = ['console']
LOGGING['loggers']['inveterate']['level'] = 'DEBUG'
LOGGING['loggers']['inveterate']['handlers'] = ['console']
LOGGING['loggers']['django']['handlers'] = ['console']
LOGGING['loggers']['celery']['handlers'] = ['console']

# CORS for development (if using separate frontend)
CORS_ALLOW_ALL_ORIGINS = True

# Relaxed throttle rates for development/testing
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {
    'admin': '10000/hour',
    'authenticated': '5000/hour',
    'public': '5000/hour',
    'service_action': '1000/hour',
    'console': '500/hour',
    'token_auth': '100/hour',
}
