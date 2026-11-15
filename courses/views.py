import calendar as pycal
import csv
import logging
from datetime import date, datetime, time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import AssignmentForm, GradeForm, SubmissionForm
from .models import Assignment, Course, Enrollment, Submission
from .security import safe_display_name

log = logging.getLogger('courses')


def role_in(user, course):
    """'teacher', 'student' or None. Superusers act as teachers everywhere."""
    if user.is_superuser:
        return Enrollment.TEACHER
    e = Enrollment.objects.filter(user=user, course=course).first()
    return e.role if e else None


def require_role(user, course, *roles):
    role = role_in(user, course)
    if role is None or (roles and role not in roles):
        raise PermissionDenied
    return role


@login_required
def dashboard(request):
    user = request.user
    if user.is_superuser:
        courses = Course.objects.all()
    else:
        courses = Course.objects.filter(enrollment__user=user)
    roles = dict(Enrollment.objects.filter(user=user).values_list('course_id', 'role'))

    # Upcoming deadlines for courses where the user is a student.
    now = timezone.now()
    student_course_ids = [cid for cid, r in roles.items() if r == Enrollment.STUDENT]
    upcoming = (Assignment.objects
                .filter(course_id__in=student_course_ids, open_at__lte=now, due_at__gte=now)
                .select_related('course'))
    submitted_ids = set(Submission.objects.filter(student=user, assignment__in=upcoming)
                        .values_list('assignment_id', flat=True))
    upcoming = [(a, a.id in submitted_ids) for a in upcoming]

    courses = courses.annotate(n_assign=Count('assignments', distinct=True))
    course_rows = [(c, 'teacher' if user.is_superuser else roles.get(c.id)) for c in courses]

    teacher_course_ids = [c.id for c, r in course_rows if r == Enrollment.TEACHER]
    to_grade = (Submission.objects
                .filter(assignment__course_id__in=teacher_course_ids, score__isnull=True)
                .count())
    return render(request, 'courses/dashboard.html', {
        'course_rows': course_rows, 'upcoming': upcoming,
        'pending': sum(1 for _, done in upcoming if not done),
        'to_grade': to_grade, 'is_teacher': bool(teacher_course_ids),
    })


MONTHS_VI = ['', 'Tháng 1', 'Tháng 2', 'Tháng 3', 'Tháng 4', 'Tháng 5', 'Tháng 6',
             'Tháng 7', 'Tháng 8', 'Tháng 9', 'Tháng 10', 'Tháng 11', 'Tháng 12']


@login_required
def calendar_view(request):
    """Month grid of deadlines in the user's courses."""
    user = request.user
    today = timezone.localdate()
    try:
        year = int(request.GET.get('y', today.year))
        month = int(request.GET.get('m', today.month))
        date(year, month, 1)
    except (TypeError, ValueError):
        year, month = today.year, today.month

    weeks = pycal.Calendar(firstweekday=0).monthdatescalendar(year, month)
    start, end = weeks[0][0], weeks[-1][-1]

    if user.is_superuser:
        course_ids = list(Course.objects.values_list('id', flat=True))
        roles = {}
    else:
        roles = dict(Enrollment.objects.filter(user=user).values_list('course_id', 'role'))
        course_ids = list(roles)

    tz = timezone.get_current_timezone()
    lo = timezone.make_aware(datetime.combine(start, time.min), tz)
    hi = timezone.make_aware(datetime.combine(end, time.max), tz)
    assignments = (Assignment.objects
                   .filter(course_id__in=course_ids, due_at__range=(lo, hi))
                   .select_related('course').order_by('due_at'))
    mine = {}
    for s in Submission.objects.filter(student=user, assignment__in=assignments):
        mine.setdefault(s.assignment_id, s)  # newest first

    now = timezone.now()
    by_day = {}
    events = []
    for a in assignments:
        is_teacher = user.is_superuser or roles.get(a.course_id) == Enrollment.TEACHER
        sub = mine.get(a.id)
        if is_teacher:
            kind = 'teach'
        elif sub:
            kind = 'done'
        elif a.due_at < now:
            kind = 'missed' if a.close_at < now else 'late'
        else:
            kind = 'todo'
        ev = {'a': a, 'kind': kind, 'day': timezone.localtime(a.due_at).date()}
        events.append(ev)
        by_day.setdefault(ev['day'], []).append(ev)

    grid = [[{'date': d, 'in_month': d.month == month, 'today': d == today,
              'events': by_day.get(d, [])} for d in week] for week in weeks]
    prev_m = (year, month - 1) if month > 1 else (year - 1, 12)
    next_m = (year, month + 1) if month < 12 else (year + 1, 1)
    return render(request, 'courses/calendar.html', {
        'grid': grid, 'title': f'{MONTHS_VI[month]}, {year}',
        'prev': prev_m, 'next': next_m, 'today': today,
        'month_events': [e for e in events if e['day'].month == month],
        'weekdays': ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'],
    })


@login_required
def course_detail(request, pk):
    course = get_object_or_404(Course, pk=pk)
    role = require_role(request.user, course)
    assignments = course.assignments.all()
    rows = []
    for a in assignments:
        mine = None
        if role == Enrollment.STUDENT:
            mine = a.submissions.filter(student=request.user).first()
        rows.append((a, mine))
    return render(request, 'courses/course_detail.html', {
        'course': course, 'role': role, 'rows': rows, 'tab': 'assign', 'n_assign': len(rows),
        'n_students': course.enrollment_set.filter(role=Enrollment.STUDENT).count(),
    })


@login_required
def assignment_create(request, course_pk):
    course = get_object_or_404(Course, pk=course_pk)
    require_role(request.user, course, Enrollment.TEACHER)
    form = AssignmentForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        a = form.save(commit=False)
        a.course = course
        a.save()
        messages.success(request, 'Đã tạo bài tập.')
        return redirect('assignment_detail', pk=a.pk)
    return render(request, 'courses/assignment_form.html', {'form': form, 'course': course})


@login_required
def assignment_detail(request, pk):
    a = get_object_or_404(Assignment.objects.select_related('course'), pk=pk)
    role = require_role(request.user, a.course)
    if role == Enrollment.TEACHER:
        return _teacher_view(request, a)
    return _student_view(request, a)


def _student_view(request, a):
    user = request.user
    history = a.submissions.filter(student=user)
    status = a.status()
    can_submit = status in ('open', 'late') and history.count() < a.max_attempts
    form = SubmissionForm(assignment=a)

    if request.method == 'POST':
        if not can_submit:
            messages.error(request, 'Không thể nộp: bài đã khoá hoặc hết lượt nộp.')
            return redirect('assignment_detail', pk=a.pk)
        form = SubmissionForm(request.POST, request.FILES, assignment=a)
        if form.is_valid():
            f = form.cleaned_data['file']
            now = timezone.now()  # server time is the source of truth
            try:
                with transaction.atomic():
                    attempt = history.count() + 1
                    Submission.objects.create(
                        assignment=a, student=user, attempt_no=attempt,
                        file=f, original_name=safe_display_name(f.name),
                        submitted_at=now, is_late=now > a.due_at,
                    )
            except IntegrityError:
                messages.error(request, 'Có lỗi khi nộp, vui lòng thử lại.')
                return redirect('assignment_detail', pk=a.pk)
            log.info('submit user=%s assignment=%s attempt=%s', user.pk, a.pk, attempt)
            messages.success(request, f'Đã nộp bài (lần {attempt}).')
            return redirect('assignment_detail', pk=a.pk)

    return render(request, 'courses/assignment_student.html', {
        'a': a, 'status': status, 'history': history,
        'can_submit': can_submit, 'form': form,
        'attempts_left': max(a.max_attempts - history.count(), 0),
    })


def _teacher_view(request, a):
    students = (Enrollment.objects.filter(course=a.course, role=Enrollment.STUDENT)
                .select_related('user').order_by('user__username'))
    latest = {}
    for s in a.submissions.all():  # ordered newest first
        latest.setdefault(s.student_id, s)
    rows = []
    for e in students:
        sub = latest.get(e.user_id)
        rows.append((e.user, sub, GradeForm(instance=sub, prefix=f's{sub.pk}') if sub else None))
    stats = {
        'total': len(rows),
        'submitted': sum(1 for _, s, _ in rows if s),
        'late': sum(1 for _, s, _ in rows if s and s.is_late),
        'graded': sum(1 for _, s, _ in rows if s and s.score is not None),
    }
    return render(request, 'courses/assignment_teacher.html', {
        'a': a, 'status': a.status(), 'rows': rows, 'stats': stats,
    })


@login_required
@require_POST
def grade(request, pk):
    sub = get_object_or_404(Submission.objects.select_related('assignment__course'), pk=pk)
    require_role(request.user, sub.assignment.course, Enrollment.TEACHER)
    form = GradeForm(request.POST, instance=sub, prefix=f's{sub.pk}')
    if form.is_valid():
        sub = form.save(commit=False)
        sub.graded_by = request.user
        sub.graded_at = timezone.now()
        sub.save()
        messages.success(request, f'Đã lưu điểm cho {sub.student.username}.')
    else:
        messages.error(request, '; '.join(e for errs in form.errors.values() for e in errs))
    return redirect('assignment_detail', pk=sub.assignment_id)


@login_required
def download(request, pk):
    sub = get_object_or_404(Submission.objects.select_related('assignment__course'), pk=pk)
    role = require_role(request.user, sub.assignment.course)
    if role != Enrollment.TEACHER and sub.student_id != request.user.id:
        log.warning('download denied user=%s submission=%s', request.user.pk, sub.pk)
        raise PermissionDenied
    # Always a download with a neutral type, never rendered in the browser.
    resp = FileResponse(sub.file.open('rb'), as_attachment=True, filename=sub.original_name,
                        content_type='application/octet-stream')
    resp['Cache-Control'] = 'private, no-store'
    return resp


@login_required
def export_csv(request, pk):
    a = get_object_or_404(Assignment.objects.select_related('course'), pk=pk)
    require_role(request.user, a.course, Enrollment.TEACHER)
    resp = HttpResponse(content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = f'attachment; filename="diem_{a.course.code}_{a.pk}.csv"'
    resp.write('﻿')  # BOM so Excel reads UTF-8
    w = csv.writer(resp)
    w.writerow(['username', 'ho_ten', 'da_nop', 'lan_nop', 'thoi_gian_nop', 'tre_han', 'diem', 'nhan_xet'])
    latest = {}
    for s in a.submissions.all():
        latest.setdefault(s.student_id, s)
    for e in (Enrollment.objects.filter(course=a.course, role=Enrollment.STUDENT)
              .select_related('user').order_by('user__username')):
        s = latest.get(e.user_id)
        w.writerow([
            e.user.username, e.user.get_full_name(),
            'x' if s else '', s.attempt_no if s else '',
            timezone.localtime(s.submitted_at).strftime('%Y-%m-%d %H:%M') if s else '',
            'x' if s and s.is_late else '',
            s.score if s and s.score is not None else '', s.feedback if s else '',
        ])
    return resp
