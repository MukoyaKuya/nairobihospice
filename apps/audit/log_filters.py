import logging

from .middleware import get_current_request


class RequestIDLogFilter(logging.Filter):
    """
    Inject the current request's correlation id into every log record so the
    `request_id` placeholder in the configured log format resolves to a real
    value instead of the '-' default.
    """

    def filter(self, record):
        request = get_current_request()
        record.request_id = getattr(request, 'request_id', '-') if request else '-'
        return True
