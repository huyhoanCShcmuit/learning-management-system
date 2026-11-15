from .models import Course


def nav_courses(request):
    """Courses for the sidebar, on every page."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}
    qs = Course.objects.all() if user.is_superuser else Course.objects.filter(enrollment__user=user)
    return {'nav_courses': list(qs.only('id', 'code', 'name').order_by('code')[:30])}
