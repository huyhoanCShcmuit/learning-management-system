"""Admin tools in the main site: bulk user import from Excel/CSV."""
import logging
import secrets

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render

from . import importer
from .models import AccountFlag, Course, Enrollment

log = logging.getLogger('courses')
User = get_user_model()
SESSION_KEY = 'user_import_preview'
_ALPHABET = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'  # no 0/O/1/l/I


def _staff_only(user):
    if not user.is_staff:
        raise PermissionDenied


def temp_password():
    return ''.join(secrets.choice(_ALPHABET) for _ in range(12))


@login_required
def import_template(request):
    _staff_only(request.user)
    resp = HttpResponse(importer.template_bytes(),
                        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resp['Content-Disposition'] = 'attachment; filename="mau_nhap_nguoi_dung.xlsx"'
    return resp


@login_required
def import_users(request):
    _staff_only(request.user)
    courses = Course.objects.order_by('code')
    ctx = {'courses': courses, 'max_rows': importer.MAX_ROWS}

    if request.method != 'POST':
        request.session.pop(SESSION_KEY, None)
        return render(request, 'manage/import_users.html', ctx)

    action = request.POST.get('action')
    if action == 'preview':
        upload = request.FILES.get('file')
        default_course = courses.filter(pk=request.POST.get('course') or 0).first()
        default_role = request.POST.get('role')
        if default_role not in (Enrollment.STUDENT, Enrollment.TEACHER):
            default_role = Enrollment.STUDENT
        if not upload:
            messages.error(request, 'Chưa chọn file.')
            return render(request, 'manage/import_users.html', ctx)
        try:
            items = importer.validate(importer.parse(upload), default_course, default_role)
        except importer.ImportError_ as e:
            messages.error(request, str(e))
            return render(request, 'manage/import_users.html', ctx)
        # Keep only plain data (no passwords exist yet) for the confirm step.
        request.session[SESSION_KEY] = {
            'default_course': default_course.pk if default_course else None,
            'default_role': default_role,
            'rows': [{k: it[k] for k in ('line', 'username', 'first_name', 'last_name', 'email', 'role')}
                     | {'courses': ', '.join(it['course_codes'])} for it in items],
        }
        ctx.update(items=items, summary=_summary(items), file_name=upload.name,
                   default_course=default_course, default_role=default_role)
        return render(request, 'manage/import_users.html', ctx)

    if action == 'confirm':
        data = request.session.pop(SESSION_KEY, None)
        if not data:
            messages.error(request, 'Phiên xem trước đã hết hạn. Vui lòng tải file lên lại.')
            return redirect('import_users')
        default_course = courses.filter(pk=data['default_course'] or 0).first()
        # Re-validate: the database may have changed since the preview.
        items = importer.validate([dict(r) for r in data['rows']], default_course, data['default_role'])
        created, enrolled, skipped = _apply(items, request.user)
        log.info('user import by=%s created=%s enrolled=%s skipped=%s',
                 request.user.pk, len(created), enrolled, skipped)
        resp = render(request, 'manage/import_done.html', {
            'created': created, 'enrolled': enrolled, 'skipped': skipped,
        })
        resp['Cache-Control'] = 'no-store'  # page shows one-time passwords
        return resp

    return redirect('import_users')


def _summary(items):
    return {
        'total': len(items),
        'new': sum(1 for i in items if i['status'] == 'new'),
        'existing': sum(1 for i in items if i['status'] == 'existing'),
        'error': sum(1 for i in items if i['status'] == 'error'),
    }


@transaction.atomic
def _apply(items, actor):
    created, enrolled, skipped = [], 0, 0
    for it in items:
        if it['status'] == 'error':
            skipped += 1
            continue
        if it['status'] == 'new':
            pw = temp_password()
            user = User(username=it['username'], first_name=it['first_name'],
                        last_name=it['last_name'], email=it['email'])
            user.set_password(pw)
            user.save()
            AccountFlag.objects.create(user=user, must_change_password=True, created_by_import=True)
            created.append({'username': user.username, 'name': user.get_full_name(), 'email': user.email,
                            'password': pw, 'courses': ', '.join(it['course_codes'])})
        else:
            user = User.objects.get(pk=it['user_id'])
        for c in it['course_objs']:
            _, new = Enrollment.objects.get_or_create(user=user, course=c, defaults={'role': it['role']})
            enrolled += new
    return created, enrolled, skipped
