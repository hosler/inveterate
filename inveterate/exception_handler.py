from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    """Normalize all error responses into ``{"detail": ...}`` format.

    Field-level validation errors are nested under
    ``{"detail": "Validation error.", "errors": {...}}``.
    """
    response = exception_handler(exc, context)

    if response is None:
        return None

    # Already has the standard {"detail": ...} shape
    if isinstance(response.data, dict) and 'detail' in response.data and len(response.data) == 1:
        return response

    # Field-level validation errors (e.g. {"field": ["error msg"]})
    if isinstance(response.data, dict) and 'detail' not in response.data:
        response.data = {
            'detail': 'Validation error.',
            'errors': response.data,
        }
    elif isinstance(response.data, list):
        response.data = {
            'detail': response.data,
        }

    return response
