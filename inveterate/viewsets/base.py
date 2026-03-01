from rest_framework import viewsets
from rest_framework.response import Response


class DynamicPageModelViewSet(viewsets.ModelViewSet):
    """Base viewset with pagination control and form rendering support"""

    def paginate_queryset(self, queryset):
        if 'no_page' in self.request.query_params and self.request.user.is_staff:
            return None

        return super().paginate_queryset(queryset)

    def list(self, request, *args, **kwargs):
        if request.accepted_renderer.format == 'form':
            # Per HTMLFormRenderer docs create a serializer with no object for an empty form
            serializer = self.get_serializer()
            return Response(serializer.data)
        else:
            return super().list(request, *args, **kwargs)


class MultiSerializerViewSetMixin(object):
    """Mixin to use different serializers for admin vs regular users"""

    def get_serializer_class(self):
        try:
            user = self.request.user
        except AttributeError:
            return self.default_serializer_class
        if user.is_staff:
            action_classes = self.admin_serializer_action_classes
        else:
            action_classes = self.serializer_action_classes
        try:
            return action_classes[self.action]
        except (KeyError, AttributeError):
            # partial_update should use the same serializer as update
            if self.action == 'partial_update':
                try:
                    return action_classes['update']
                except (KeyError, AttributeError, TypeError):
                    pass
            return self.default_serializer_class
