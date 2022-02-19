from django.conf import settings
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import User
import requests
from django.apps import apps

ConfigSettings = apps.get_model('core', 'ConfigSettings')


class BlestaBackend(BaseBackend):

    def authenticate(self, request, username=None, password=None):
        try:
            api_user = ConfigSettings.objects.get(name="BLESTA_API_USER")
            api_key = ConfigSettings.objects.get(name="BLESTA_API_KEY")
            host = ConfigSettings.objects.get(name="BLESTA_HOSTNAME")
        except ConfigSettings.DoesNotExist:
            return None

        params = (
            ('username', username),
        )
        try:
            response = requests.get(f'https://{host.value}/api/users/getByUsername.json',
                                    params=params,
                                    auth=(api_user.value, api_key.value))
        except requests.exceptions.ConnectionError:
            return None
        try:
            user_id = response.json()["response"]["id"]
        except KeyError:
            return None
        params = (
            ('password', password),
            ('user_id', user_id)
        )
        response = requests.get(f'https://{host}/api/users/validatePasswordEquals.json',
                                params=params,
                                auth=(api_user.value, api_key.value))
        valid = response.json()["response"]
        if valid:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                # Create a new user. There's no need to set a password
                # because only the password from settings.py is checked.
                user = User(username=username)
                # user.is_staff = True
                # user.is_superuser = True
                user.save()
            return user
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
