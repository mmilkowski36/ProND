from django.utils import timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

FALLBACK_TZ = ZoneInfo("America/New_York")


class UserTimezoneMiddleware:
    """Activates the current request's timezone from the 'tz' cookie.

    The cookie is set client-side (see templates/base.html) to the browser's
    IANA timezone name. If missing or invalid, falls back to America/New_York.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tzname = request.COOKIES.get("tz")
        try:
            timezone.activate(ZoneInfo(tzname) if tzname else FALLBACK_TZ)
        except (ZoneInfoNotFoundError, ValueError):
            timezone.activate(FALLBACK_TZ)
        return self.get_response(request)
