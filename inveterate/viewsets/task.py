from celery.result import AsyncResult
from rest_framework.response import Response
from rest_framework.views import APIView


class TaskStatusView(APIView):
    def get(self, request, task_id):
        result = AsyncResult(task_id)
        data = {
            'task_id': task_id,
            'status': result.status,
        }
        if result.successful():
            data['result'] = result.result
        elif result.failed():
            data['error'] = str(result.result)
        return Response(data)
