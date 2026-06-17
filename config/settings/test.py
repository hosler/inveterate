"""
Test settings for Inveterate project.
Uses SQLite in-memory, eager Celery, silenced logging.
"""
from .base import *  # noqa: F401,F403

# Fixed throwaway key so EncryptedCharField works without external config.
FIELD_ENCRYPTION_KEY = "eu6XmlmFpkmCXOQvMTLVHVwbNcTh6Zaez3SZW1p9chc="

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

# In-memory channel layer — no Redis needed for tests
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
