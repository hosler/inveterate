from rest_framework.permissions import BasePermission, SAFE_METHODS


class ReadOnly(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user.is_authenticated and
            request.method in SAFE_METHODS
        )


class ReadOnlyAnonymous(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.method in SAFE_METHODS
        )


class IsAuthenticated(BasePermission):
    def has_permission(self, request, view):
        if view.action in ['provision_billing', 'destroy', 'calculate']:
            return False

        return bool(
            request.user and
            request.user.is_authenticated
        )
