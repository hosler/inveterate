from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser
from django.contrib.auth import get_user_model
from .serializers import UserDetailsSerializerWithType

# Get the UserModel
UserModel = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    serializer_class = UserDetailsSerializerWithType
    permission_classes = (IsAdminUser,)

    def get_queryset(self):
        return UserModel.objects.all()
