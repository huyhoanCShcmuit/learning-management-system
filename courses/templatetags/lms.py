from django import template
from django.utils import timezone

register = template.Library()


@register.filter
def con_lai(dt):
    """Thời gian còn lại đến dt, tiếng Việt: '4 ngày 3 giờ', '2 giờ 15 phút'."""
    secs = int((dt - timezone.now()).total_seconds())
    if secs <= 0:
        return '0 phút'
    days, rem = divmod(secs, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        return f'{days} ngày {hours} giờ' if hours else f'{days} ngày'
    if hours:
        return f'{hours} giờ {minutes} phút'
    return f'{minutes} phút'


@register.filter
def truoc(dt):
    """Thời gian đã trôi qua, tiếng Việt: 'vừa xong', '5 phút trước', '3 ngày trước'."""
    secs = int((timezone.now() - dt).total_seconds())
    if secs < 60:
        return 'vừa xong'
    for size, unit in ((86400 * 365, 'năm'), (86400 * 30, 'tháng'), (86400, 'ngày'), (3600, 'giờ'), (60, 'phút')):
        if secs >= size:
            return f'{secs // size} {unit} trước'
