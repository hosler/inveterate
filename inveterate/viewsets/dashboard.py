from django.contrib.auth import get_user_model
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.serializers import ModelSerializer

from .base import DynamicPageModelViewSet
from .. import models

UserModel = get_user_model()


class CustomerViewSet(DynamicPageModelViewSet):
    permission_classes = [IsAdminUser]
    throttle_scope = 'admin'
    queryset = UserModel.objects.all().order_by('pk')
    search_fields = ['username', 'email']
    ordering_fields = ['id', 'username', 'date_joined']

    def get_serializer_class(self):
        # Create a dynamic serializer for UserModel
        class UserSerializer(ModelSerializer):
            class Meta:
                model = UserModel
                fields = ['id', 'first_name', 'last_name', 'email', 'username', 'is_active', 'date_joined']
                read_only_fields = ['id', 'date_joined']

        return UserSerializer


class DashboardViewSet(viewsets.ViewSet):
    permission_classes = [IsAdminUser]
    throttle_scope = 'admin'

    @action(methods=['get'], detail=False)
    def summary(self, request):
        user_count = UserModel.objects.count()
        plan_count = models.Plan.objects.count()
        ip_count = models.IP.objects.count()
        template_count = models.Template.objects.count()
        service_count = models.Service.objects.count()
        node_count = models.Node.objects.count()
        data = {
            'users': user_count,
            'plans': plan_count,
            'ips': ip_count,
            'templates': template_count,
            'services': service_count,
            'nodes': node_count
        }
        return Response(data)
