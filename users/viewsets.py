from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import BasePermission, IsAdminUser, SAFE_METHODS
from django.contrib.auth import get_user_model
from .serializers import UserDetailsSerializerWithType

# Get the UserModel
UserModel = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    serializer_class = UserDetailsSerializerWithType
    permission_classes = (IsAdminUser,)

    def get_queryset(self):
        return UserModel.objects.all()
