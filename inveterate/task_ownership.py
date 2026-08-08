"""
Task ownership recording, used to close the task-status IDOR
(see `viewsets/task.py::TaskStatusView`).

`task_id` (a Celery/UUID string) carries no information about who dispatched
it, so anyone authenticated could otherwise poll GET /api/v1/tasks/<id>/ for
any other user's task. Dispatch sites should call `record_task_owner()`
immediately after `.delay()` so `TaskStatusView` can check ownership.

Usage at each dispatch site (viewsets/service.py, viewsets/resource.py, or
anywhere else a task is queued on behalf of a specific request/user):

    from ..task_ownership import record_task_owner

    result = some_task.delay(...)
    record_task_owner(result.id, request.user)

Only one line is needed per dispatch site; failures (e.g. AnonymousUser,
or the DispatchedTask write itself) are swallowed so a bug here can never
block task dispatch.
"""
import logging

logger = logging.getLogger(__name__)


def record_task_owner(task_id, user):
    """Record that `user` dispatched Celery task `task_id`.

    No-ops (returns None) if `user` is missing/anonymous. Never raises —
    a failure to record ownership should not block task dispatch; it will
    just mean the task's status is not readable by anyone but staff.
    """
    if not task_id or user is None or not getattr(user, 'is_authenticated', False):
        return None

    from .models import DispatchedTask

    try:
        obj, _ = DispatchedTask.objects.update_or_create(
            task_id=str(task_id), defaults={'owner': user},
        )
        return obj
    except Exception:
        logger.exception("Failed to record task owner for task_id=%s", task_id)
        return None


def user_owns_task(task_id, user):
    """Return True if `user` is the recorded owner of `task_id`.

    Returns False (not an error) if there is no ownership record at all —
    callers should decide the appropriate fallback (e.g. TaskStatusView
    treats "no record" as "not visible to non-staff").
    """
    from .models import DispatchedTask

    if not task_id or user is None or not getattr(user, 'is_authenticated', False):
        return False
    return DispatchedTask.objects.filter(task_id=str(task_id), owner=user).exists()
