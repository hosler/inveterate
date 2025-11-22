"""
Development settings for Inveterate project.
"""
from .base import *

# Override for development
DEBUG = True

ALLOWED_HOSTS = ['*']

# Development-specific apps
INSTALLED_APPS += [
    'django_extensions',  # Optional: useful dev tools
]

# Simplified logging for development
LOGGING['root']['level'] = 'DEBUG'
LOGGING['loggers']['inveterate']['level'] = 'DEBUG'

# CORS for development (if using separate frontend)
# Uncomment if needed:
# INSTALLED_APPS += ['corsheaders']
# MIDDLEWARE.insert(0, 'corsheaders.middleware.CorsMiddleware')
# CORS_ALLOW_ALL_ORIGINS = True
