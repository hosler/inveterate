"""
Test settings for Inveterate project.
Uses SQLite in-memory, eager Celery, silenced logging.
"""
from .base import *  # noqa: F401,F403

# SQLite in-memory database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Eager Celery — no broker needed
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Remove dev-only apps that may not be installed
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != 'django_extensions']

# Silence logging during tests
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'handlers': {
        'null': {
            'class': 'logging.NullHandler',
        },
    },
    'root': {
        'handlers': ['null'],
        'level': 'CRITICAL',
    },
}

# Faster password hashing for tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
