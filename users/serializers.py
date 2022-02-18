from django.contrib.auth import get_user_model
from rest_auth.serializers import UserDetailsSerializer

# Get the UserModel
UserModel = get_user_model()


class UserDetailsSerializerWithType(UserDetailsSerializer):
    """
    User model w/o password
    """
    class Meta:
        model = UserModel
        fields = ('pk', 'username', 'email', 'first_name', 'last_name', 'is_staff')
        read_only_fields = ('pk', 'email', 'is_staff')
