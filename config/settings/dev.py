"""
Development settings for Inveterate project.
"""
from .base import *

# Override for development
DEBUG = True

ALLOWED_HOSTS = ['*']

# Cookie domain for console access — lets PVEAuthCookie reach Proxmox
# on sibling subdomains (e.g., taban.hosnet.internal).
SESSION_COOKIE_DOMAIN = '.hosnet.internal'
CSRF_COOKIE_DOMAIN = '.hosnet.internal'

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
