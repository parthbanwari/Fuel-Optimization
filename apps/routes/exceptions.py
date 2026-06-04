from rest_framework.response import Response
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """Ensure all unhandled errors return a consistent JSON shape."""
    response = exception_handler(exc, context)

    if response is not None:
        response.data = {
            "error": response.data
            if isinstance(response.data, str)
            else response.data.get("detail", response.data),
        }

    return response
