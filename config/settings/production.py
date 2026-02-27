"""
Production settings for Inveterate project.
"""
from .base import *

# Security settings for production
DEBUG = False

# Must be explicitly set in production
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')

# Security middleware
SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'off').lower() in ('on', 'true', '1')
SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '0'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = 'DENY'

# Production logging - less verbose
LOGGING['root']['level'] = 'INFO'
LOGGING['loggers']['inveterate']['level'] = 'INFO'
LOGGING['loggers']['django']['level'] = 'WARNING'

# Ensure SECRET_KEY is set
if not os.environ.get('SECRET_KEY'):
    raise ValueError("SECRET_KEY environment variable must be set in production")

