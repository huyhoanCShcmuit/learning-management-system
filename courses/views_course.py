"""Course participants, gradebook and per-student progress (Moodle-like)."""
import csv
import logging
import re
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Course, Enrollment, Submission
from .views import require_role

log = logging.getLogger('courses')
User = get_user_model()


def _latest_submissions(course):
    """{(assignment_id, student_id): newest Submission} for a course."""
    latest = {}
    for s in (Submission.objects.filter(assignment__course=course)
              .only('id', 'assignment_id', 'student_id', 'score', 'is_late', 'submitted_at', 'graded_at')
              .order_by('-submitted_at')):
        latest.setdefault((s.assignment_id, s.student_id), s)
    return latest


def _progress(student_id, assignments, latest):
    """Submitted count and average score in percent (graded work only)."""
    submitted, pct = 0, []
    for a in assignments:
        s = latest.get((a.id, student_id))
        if s:
            submitted += 1
            if s.score is not None and a.max_score:
                pct.append(Decimal(s.score) / a.max_score * 100)
    avg = round(sum(pct) / len(pct), 1) if pct else None
    return submitted, avg


def _cell(a, s, now):
    """Status of one student on one assignment."""
    if s:
        if s.score is not None:
            return 'graded'
        return 'late' if s.is_late else 'submitted'
    if now > a.close_at:
        return 'missing'
    if now > a.due_at:
        return 'overdue'   # past due, late submissions still accepted
    return 'pending'


@login_required
def course_members(request, pk):
    course = get_object_or_404(Course, pk=pk)
    require_role(request.user, course, Enrollment.TEACHER)

    if request.method == 'POST':
        return _members_post(request, course)

    q = request.GET.get('q', '').strip()[:100]
    role = request.GET.get('role', '')
    members = (Enrollment.objects.filter(course=course).select_related('user')
               .order_by('role', 'user__last_name', 'user__first_name', 'user__username'))
    if role in (Enrollment.STUDENT, Enrollment.TEACHER):
        members = members.filter(role=role)
    if q:
        members = members.filter(Q(user__username__icontains=q) | Q(user__first_name__icontains=q)
                                 | Q(user__last_name__icontains=q) | Q(user__email__icontains=q))

    assignments = list(course.assignments.all())
    latest = _latest_submissions(course)
    rows = []
    for e in members:
        submitted, avg = _progress(e.user_id, assignments, latest) if e.role == Enrollment.STUDENT else (None, None)
        rows.append({'e': e, 'submitted': submitted, 'avg': avg})

    counts = dict(Enrollment.objects.filter(course=course).values_list('role').annotate(n=Count('id')))
    return render(request, 'courses/course_members.html', {
        'course': course, 'role': Enrollment.TEACHER, 'tab': 'members', 'rows': rows,
        'n_students': counts.get(Enrollment.STUDENT, 0), 'n_teachers': counts.get(Enrollment.TEACHER, 0),
        'n_assign': len(assignments), 'q': q, 'role_filter': role,
    })


def _members_post(request, course):
    action = request.POST.get('action')
    if action == 'enrol':
        names = [n for n in re.split(r'[\s,;]+', request.POST.get('usernames', '')) if n][:200]
        role = request.POST.get('role')
        if role not in (Enrollment.STUDENT, Enrollment.TEACHER):
            role = Enrollment.STUDENT
        # Only superusers may add teachers; teachers can add students.
        if role == Enrollment.TEACHER and not request.user.is_superuser:
            raise PermissionDenied
        found = {}
        for n in names:
            u = User.objects.filter(username__iexact=n, is_active=True).first()
            if u:
                found[n.lower()] = u
        added, already = 0, 0
        for u in found.values():
            _, created = Enrollment.objects.get_or_create(user=u, course=course, defaults={'role': role})
            added += created
            already += not created
        missing = [n for n in names if n.lower() not in found]
        if added:
            messages.success(request, f'Đã ghi danh {added} người.')
            log.info('enrol course=%s by=%s added=%s', course.pk, request.user.pk, added)
        if already:
            messages.success(request, f'{already} người đã có trong khoá.')
        if missing:
            messages.error(request, 'Không tìm thấy: ' + ', '.join(missing[:20]))
    elif action == 'remove':
        e = get_object_or_404(Enrollment, pk=request.POST.get('enrollment'), course=course)
        if e.user_id == request.user.id:
            messages.error(request, 'Không thể tự xoá mình khỏi khoá.')
        elif e.role == Enrollment.TEACHER and not request.user.is_superuser:
            raise PermissionDenied
        else:
            name = e.user.get_full_name() or e.user.username
            e.delete()  # submissions are kept
            log.info('unenrol course=%s user=%s by=%s', course.pk, e.user_id, request.user.pk)
            messages.success(request, f'Đã xoá {name} khỏi khoá. Bài nộp cũ vẫn được giữ.')
    return redirect('course_members', pk=course.pk)


@login_required
def gradebook(request, pk):
    course = get_object_or_404(Course, pk=pk)
    role = require_role(request.user, course)
    if role != Enrollment.TEACHER:
        return redirect('member_progress', pk=course.pk, user_id=request.user.pk)

    assignments = list(course.assignments.all())
    students = list(Enrollment.objects.filter(course=course, role=Enrollment.STUDENT)
                    .select_related('user').order_by('user__last_name', 'user__first_name', 'user__username'))
    latest = _latest_submissions(course)
    now = timezone.now()

    rows = []
    for e in students:
        cells = []
        for a in assignments:
            s = latest.get((a.id, e.user_id))
            cells.append({'a': a, 's': s, 'st': _cell(a, s, now)})
        submitted, avg = _progress(e.user_id, assignments, latest)
        rows.append({'u': e.user, 'cells': cells, 'submitted': submitted, 'avg': avg})

    # Column summaries: how many submitted, class average.
    cols = []
    for i, a in enumerate(assignments):
        scores = [r['cells'][i]['s'].score for r in rows if r['cells'][i]['s'] and r['cells'][i]['s'].score is not None]
        cols.append({'a': a, 'n': sum(1 for r in rows if r['cells'][i]['s']),
                     'avg': round(sum(scores) / len(scores), 2) if scores else None})

    if request.GET.get('format') == 'csv':
        resp = HttpResponse(content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = f'attachment; filename="bang_diem_{course.code}.csv"'
        resp.write('﻿')
        w = csv.writer(resp)
        w.writerow(['username', 'ho_ten'] + [a.title for a in assignments] + ['da_nop', 'trung_binh_%'])
        for r in rows:
            w.writerow([r['u'].username, r['u'].get_full_name()]
                       + [c['s'].score if c['s'] and c['s'].score is not None else ('nộp' if c['s'] else '')
                          for c in r['cells']]
                       + [f"{r['submitted']}/{len(assignments)}", r['avg'] if r['avg'] is not None else ''])
        return resp

    return render(request, 'courses/gradebook.html', {
        'course': course, 'role': role, 'tab': 'grades', 'rows': rows, 'cols': cols,
        'n_students': len(students), 'n_assign': len(assignments),
    })


@login_required
def member_progress(request, pk, user_id):
    course = get_object_or_404(Course, pk=pk)
    role = require_role(request.user, course)
    if role != Enrollment.TEACHER and request.user.pk != user_id:
        raise PermissionDenied
    e = get_object_or_404(Enrollment.objects.select_related('user'), course=course, user_id=user_id)

    assignments = list(course.assignments.all())
    latest = _latest_submissions(course)
    now = timezone.now()
    items = [{'a': a, 's': latest.get((a.id, user_id)), 'st': _cell(a, latest.get((a.id, user_id)), now)}
             for a in assignments]
    submitted, avg = _progress(user_id, assignments, latest)
    return render(request, 'courses/member_progress.html', {
        'course': course, 'role': role, 'tab': 'grades' if role != Enrollment.TEACHER else 'members',
        'member': e, 'items': items, 'submitted': submitted, 'avg': avg, 'n_assign': len(assignments),
        'missing': sum(1 for i in items if i['st'] == 'missing'),
    })
