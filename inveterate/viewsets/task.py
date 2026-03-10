from celery.result import AsyncResult
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class TaskStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
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
