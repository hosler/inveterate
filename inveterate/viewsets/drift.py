from rest_framework import permissions, viewsets

from ..models import DriftFinding
from ..serializers import DriftFindingSerializer


class DriftFindingViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DriftFindingSerializer
    permission_classes = (permissions.IsAdminUser,)

    def get_queryset(self):
        queryset = DriftFinding.objects.all()
        resolved = self.request.query_params.get("resolved")
        if resolved is not None:
            value = resolved.lower()
            if value in {"true", "1"}:
                queryset = queryset.filter(resolved_at__isnull=False)
            elif value in {"false", "0"}:
                queryset = queryset.filter(resolved_at__isnull=True)
        return queryset
