from django.contrib.auth import get_user_model
from dj_rest_auth.serializers import UserDetailsSerializer
from rest_framework.serializers import SerializerMethodField

# Get the UserModel
UserModel = get_user_model()


class UserDetailsSerializerWithType(UserDetailsSerializer):
    __str__ = SerializerMethodField('display_name')

    def display_name(self, obj):
        return obj.username

    class Meta:
        model = UserModel
        fields = ('pk', 'username', 'email', 'first_name', 'last_name', 'is_staff', '__str__')
        read_only_fields = ('pk', 'email', 'is_staff')
