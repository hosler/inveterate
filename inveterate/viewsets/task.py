from celery.result import AsyncResult
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..task_ownership import user_owns_task


class TaskStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        user = request.user
        is_privileged = user.is_staff or user.is_superuser
        if not is_privileged and not user_owns_task(task_id, user):
            # 404, not 403: don't reveal whether the task_id exists at all.
            raise NotFound()

        result = AsyncResult(task_id)
        data = {
            'task_id': task_id,
            'status': result.status,
        }
        if result.successful():
            data['result'] = result.result
        elif result.failed():
            data['error'] = "Task failed. Please try again or contact support."
        return Response(data)
