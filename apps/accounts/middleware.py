from django.utils import timezone


class LastSeenMiddleware:
    """Update user's last_seen timestamp on every request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated:
            request.user.__class__.objects.filter(pk=request.user.pk).update(
                last_seen=timezone.now()
            )
        return response
