from django.shortcuts import redirect
from django.conf import settings


def anonymous_required(func):
    def as_view(request, *args, **kwargs):
        redirect_to = kwargs.get('next', settings.ACCOUNT_LOGIN_REDIRECT_URL)
        if request.user.is_authenticated:
            return redirect(redirect_to)
        response = func(request, *args, **kwargs)
        return response
    return as_view