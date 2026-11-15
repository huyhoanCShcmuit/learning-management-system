import shutil
import tempfile
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import AccountFlag, Assignment, Course, Enrollment, Submission

TMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TMP_MEDIA)
class SubmitFlowTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def setUp(self):
        now = timezone.now()
        self.gv = User.objects.create_user('gv', password='x')
        self.hs = User.objects.create_user('hs', password='x')
        self.other = User.objects.create_user('other', password='x')  # not enrolled
        self.c = Course.objects.create(code='C1', name='Course')
        Enrollment.objects.create(user=self.gv, course=self.c, role=Enrollment.TEACHER)
        Enrollment.objects.create(user=self.hs, course=self.c)
        self.open = Assignment.objects.create(
            course=self.c, title='open', open_at=now - timedelta(days=1),
            due_at=now + timedelta(days=1), allowed_ext='pdf')
        self.late = Assignment.objects.create(
            course=self.c, title='late', open_at=now - timedelta(days=3),
            due_at=now - timedelta(days=1), cutoff_at=now + timedelta(days=1), allowed_ext='pdf')
        self.closed = Assignment.objects.create(
            course=self.c, title='closed', open_at=now - timedelta(days=3),
            due_at=now - timedelta(days=1), allowed_ext='pdf')

    def submit(self, a, name='bai.pdf'):
        return self.client.post(reverse('assignment_detail', args=[a.pk]),
                                {'file': SimpleUploadedFile(name, b'%PDF-1.4 test')})

    def test_submit_then_replace_keeps_one_submission(self):
        import os
        self.client.force_login(self.hs)
        self.submit(self.open, 'ban1.pdf')
        first = Submission.objects.get(assignment=self.open, student=self.hs)
        old_path = first.file.path
        self.submit(self.open, 'ban2.pdf')
        subs = Submission.objects.filter(assignment=self.open, student=self.hs)
        self.assertEqual(subs.count(), 1)
        s = subs.get()
        self.assertEqual(s.original_name, 'ban2.pdf')
        self.assertEqual(s.created_at, first.created_at)       # first submit time kept
        self.assertGreaterEqual(s.submitted_at, first.submitted_at)
        self.assertFalse(os.path.exists(old_path))              # replaced file removed
        self.assertFalse(s.is_late)

    def test_cannot_edit_after_lock(self):
        self.client.force_login(self.hs)
        self.submit(self.late, 'truoc.pdf')
        Assignment.objects.filter(pk=self.late.pk).update(cutoff_at=timezone.now() - timedelta(minutes=1))
        self.submit(self.late, 'sau.pdf')
        self.assertEqual(Submission.objects.get(assignment=self.late).original_name, 'truoc.pdf')

    def test_teacher_edits_due_date_and_late_flags_follow(self):
        self.client.force_login(self.hs)
        self.submit(self.late)
        self.assertTrue(Submission.objects.get(assignment=self.late).is_late)
        later = timezone.localtime(timezone.now() + timedelta(days=3)).strftime('%Y-%m-%dT%H:%M')
        data = {'title': 'late', 'description': '', 'open_at': timezone.localtime(self.late.open_at).strftime('%Y-%m-%dT%H:%M'),
                'due_at': later, 'cutoff_at': '', 'allowed_ext': 'pdf', 'max_size_mb': 20, 'max_score': 10}
        url = reverse('assignment_edit', args=[self.late.pk])
        self.assertEqual(self.client.post(url, data).status_code, 403)    # students cannot edit
        self.client.force_login(self.gv)
        r = self.client.post(url, data)
        self.assertRedirects(r, reverse('assignment_detail', args=[self.late.pk]))
        self.assertFalse(Submission.objects.get(assignment=self.late).is_late)

    def test_teacher_page_explains_no_upload(self):
        self.client.force_login(self.gv)
        self.assertContains(self.client.get(reverse('assignment_detail', args=[self.open.pk])), 'vai trò <b>giáo viên</b>')

    def test_wrong_extension_rejected(self):
        self.client.force_login(self.hs)
        self.submit(self.open, 'virus.exe')
        self.assertFalse(Submission.objects.exists())

    def test_late_and_closed(self):
        self.client.force_login(self.hs)
        self.submit(self.late)
        self.submit(self.closed)
        self.assertTrue(Submission.objects.get(assignment=self.late).is_late)
        self.assertFalse(Submission.objects.filter(assignment=self.closed).exists())

    def test_not_enrolled_forbidden(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('course_detail', args=[self.c.pk])).status_code, 403)
        self.assertEqual(self.submit(self.open).status_code, 403)

    def test_grade_and_download_permissions(self):
        self.client.force_login(self.hs)
        self.submit(self.open)
        sub = Submission.objects.get()
        r = self.client.post(reverse('grade', args=[sub.pk]), {f's{sub.pk}-score': '10'})
        self.assertEqual(r.status_code, 403)  # student cannot grade
        self.client.force_login(self.gv)
        self.client.post(reverse('grade', args=[sub.pk]),
                         {f's{sub.pk}-score': '8.5', f's{sub.pk}-feedback': 'ok'})
        sub.refresh_from_db()
        self.assertEqual(float(sub.score), 8.5)
        self.assertEqual(self.client.get(reverse('download', args=[sub.pk])).status_code, 200)
        self.assertIn('hs', self.client.get(reverse('export_csv', args=[self.open.pk])).content.decode())
        Enrollment.objects.create(user=self.other, course=self.c)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('download', args=[sub.pk])).status_code, 403)


@override_settings(MEDIA_ROOT=TMP_MEDIA)
class SecurityTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.hs = User.objects.create_user('hs', password='correct-horse-1')
        c = Course.objects.create(code='C1', name='Course')
        Enrollment.objects.create(user=self.hs, course=c)
        self.a = Assignment.objects.create(course=c, title='a', open_at=now - timedelta(days=1),
                                           due_at=now + timedelta(days=1), allowed_ext='pdf,py')

    def test_fake_pdf_rejected(self):
        self.client.force_login(self.hs)
        self.client.post(reverse('assignment_detail', args=[self.a.pk]),
                         {'file': SimpleUploadedFile('bai.pdf', b'MZ\x90\x00 not a pdf')})
        self.assertFalse(Submission.objects.exists())

    def test_text_file_with_binary_rejected(self):
        self.client.force_login(self.hs)
        self.client.post(reverse('assignment_detail', args=[self.a.pk]),
                         {'file': SimpleUploadedFile('main.py', b'print(1)\x00\x01')})
        self.assertFalse(Submission.objects.exists())

    def test_security_headers(self):
        r = self.client.get(reverse('login'))
        self.assertIn("script-src 'self'", r['Content-Security-Policy'])
        self.assertEqual(r['X-Frame-Options'], 'DENY')
        self.assertEqual(r['X-Content-Type-Options'], 'nosniff')


class CalendarTests(TestCase):
    def test_calendar_shows_only_my_courses(self):
        now = timezone.now()
        hs = User.objects.create_user('hs')
        mine = Course.objects.create(code='M1', name='Mine')
        other = Course.objects.create(code='O1', name='Other')
        Enrollment.objects.create(user=hs, course=mine)
        Assignment.objects.create(course=mine, title='bai-cua-toi', due_at=now)
        Assignment.objects.create(course=other, title='bai-khoa-khac', due_at=now)
        self.client.force_login(hs)
        r = self.client.get(reverse('calendar'))
        self.assertContains(r, 'bai-cua-toi')
        self.assertNotContains(r, 'bai-khoa-khac')
        self.assertEqual(self.client.get(reverse('calendar') + '?y=abc&m=13').status_code, 200)


@override_settings(MEDIA_ROOT=TMP_MEDIA)
class CourseAdminPagesTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.gv = User.objects.create_user('gv')
        self.hs = User.objects.create_user('hs', first_name='An')
        self.hs2 = User.objects.create_user('hs2')
        self.new = User.objects.create_user('moi')
        self.c = Course.objects.create(code='C1', name='Course')
        Enrollment.objects.create(user=self.gv, course=self.c, role=Enrollment.TEACHER)
        Enrollment.objects.create(user=self.hs, course=self.c)
        Enrollment.objects.create(user=self.hs2, course=self.c)
        self.a = Assignment.objects.create(course=self.c, title='A1', open_at=now - timedelta(days=1),
                                           due_at=now + timedelta(days=1))

    def test_members_teacher_only(self):
        self.client.force_login(self.hs)
        self.assertEqual(self.client.get(reverse('course_members', args=[self.c.pk])).status_code, 403)
        self.client.force_login(self.gv)
        r = self.client.get(reverse('course_members', args=[self.c.pk]))
        self.assertContains(r, 'hs2')

    def test_teacher_enrols_and_removes_student(self):
        self.client.force_login(self.gv)
        url = reverse('course_members', args=[self.c.pk])
        self.client.post(url, {'action': 'enrol', 'usernames': 'MOI, khongcoai', 'role': 'student'})
        self.assertTrue(Enrollment.objects.filter(user=self.new, course=self.c, role='student').exists())
        e = Enrollment.objects.get(user=self.new, course=self.c)
        self.client.post(url, {'action': 'remove', 'enrollment': e.pk})
        self.assertFalse(Enrollment.objects.filter(pk=e.pk).exists())

    def test_teacher_cannot_add_teacher(self):
        self.client.force_login(self.gv)
        r = self.client.post(reverse('course_members', args=[self.c.pk]),
                             {'action': 'enrol', 'usernames': 'moi', 'role': 'teacher'})
        self.assertEqual(r.status_code, 403)

    def test_gradebook_and_progress_permissions(self):
        self.client.force_login(self.gv)
        self.assertContains(self.client.get(reverse('gradebook', args=[self.c.pk])), 'hs2')
        self.assertEqual(self.client.get(reverse('gradebook', args=[self.c.pk]) + '?format=csv').status_code, 200)
        self.client.force_login(self.hs)
        r = self.client.get(reverse('gradebook', args=[self.c.pk]))
        self.assertRedirects(r, reverse('member_progress', args=[self.c.pk, self.hs.pk]))
        self.assertEqual(self.client.get(reverse('member_progress', args=[self.c.pk, self.hs2.pk])).status_code, 403)

    def test_any_format_when_blank(self):
        self.a.allowed_ext = ''
        self.a.save()
        self.client.force_login(self.hs)
        url = reverse('assignment_detail', args=[self.a.pk])
        self.client.post(url, {'file': SimpleUploadedFile('bao_cao.docx', b'PK\x03\x04 docx')})
        self.client.post(url, {'file': SimpleUploadedFile('virus.exe', b'MZ\x90')})
        self.client.post(url, {'file': SimpleUploadedFile('fake.docx', b'not a zip')})
        self.assertEqual([s.original_name for s in Submission.objects.all()], ['bao_cao.docx'])


class AccountTests(TestCase):
    def setUp(self):
        self.u = User.objects.create_user('hs', email='a@x.vn')
        User.objects.create_user('khac', email='b@x.vn')

    def test_profile_and_settings(self):
        self.client.force_login(self.u)
        self.assertEqual(self.client.get(reverse('profile')).status_code, 200)
        self.client.post(reverse('settings'), {'first_name': 'Bình', 'last_name': 'Trần', 'email': 'A2@x.vn'})
        self.u.refresh_from_db()
        self.assertEqual((self.u.first_name, self.u.email), ('Bình', 'a2@x.vn'))
        r = self.client.post(reverse('settings'), {'first_name': 'B', 'last_name': '', 'email': 'b@x.vn'})
        self.assertContains(r, 'đã được tài khoản khác')
        r = self.client.get(reverse('password_change'))
        self.assertContains(r, 'Huỷ')                    # our template, not Django admin's
        self.assertNotContains(r, 'Django')
        self.assertContains(self.client.get('/khong-ton-tai/'), 'Không tìm thấy trang', status_code=404)


class StatusCellTests(TestCase):
    def test_overdue_vs_missing(self):
        from .views_course import _cell
        now = timezone.now()
        late_ok = Assignment(due_at=now - timedelta(hours=1), cutoff_at=now + timedelta(hours=1))
        closed = Assignment(due_at=now - timedelta(hours=2))
        future = Assignment(due_at=now + timedelta(hours=2))
        self.assertEqual(_cell(late_ok, None, now), 'overdue')
        self.assertEqual(_cell(closed, None, now), 'missing')
        self.assertEqual(_cell(future, None, now), 'pending')


class PublicPagesTests(TestCase):
    def test_public_pages_and_footer(self):
        for url in ['/help/', '/privacy/', '/login/']:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertContains(r, 'site-footer')
        self.assertContains(self.client.get('/robots.txt'), 'Disallow: /')
        self.assertEqual(self.client.get('/favicon.ico').status_code, 301)

    def test_footer_when_logged_in(self):
        self.client.force_login(User.objects.create_user('u'))
        r = self.client.get('/')
        self.assertContains(r, 'site-footer')
        self.assertContains(r, 'aria-current="page"')


class UserImportTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('quantri', is_staff=True)
        self.c = Course.objects.create(code='WEB101', name='Web')
        User.objects.create_user('daco', email='daco@x.vn')

    def _xlsx(self, rows):
        import io
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        for r in rows:
            ws.append(r)
        buf = io.BytesIO()
        wb.save(buf)
        return SimpleUploadedFile('ds.xlsx', buf.getvalue())

    def test_staff_only(self):
        self.client.force_login(User.objects.create_user('hs'))
        self.assertEqual(self.client.get(reverse('import_users')).status_code, 403)
        self.assertEqual(self.client.get(reverse('import_template')).status_code, 403)

    def test_template_downloads(self):
        self.client.force_login(self.admin)
        r = self.client.get(reverse('import_template'))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'PK'))

    def test_preview_then_confirm(self):
        self.client.force_login(self.admin)
        f = self._xlsx([
            ['Tên đăng nhập', 'Họ', 'Tên', 'Email', 'Vai trò', 'Mã khoá'],
            [22520001, 'Nguyễn Văn', 'An', 'an@x.vn', 'học viên', 'web101'],
            ['daco', '', '', '', '', 'WEB101'],
            ['loi xau', '', '', 'khong-phai-email', 'hiệu trưởng', 'KHONGCO'],
            ['22520001', '', '', '', '', ''],
        ])
        r = self.client.post(reverse('import_users'), {'action': 'preview', 'file': f})
        self.assertContains(r, 'Tạo mới')
        self.assertContains(r, 'Trùng tên đăng nhập trong file')
        self.assertContains(r, 'Không có khoá')
        self.assertFalse(User.objects.filter(username='22520001').exists())  # nothing created yet

        r = self.client.post(reverse('import_users'), {'action': 'confirm'})
        self.assertEqual(r['Cache-Control'], 'no-store')
        u = User.objects.get(username='22520001')
        self.assertEqual((u.last_name, u.first_name, u.email), ('Nguyễn Văn', 'An', 'an@x.vn'))
        self.assertTrue(u.flags.must_change_password)
        self.assertTrue(Enrollment.objects.filter(user=u, course=self.c, role='student').exists())
        self.assertTrue(Enrollment.objects.filter(user__username='daco', course=self.c).exists())
        self.assertFalse(User.objects.filter(username='loi xau').exists())
        # The one-time password shown on the page actually works.
        import re
        pw = re.search(r'<td class="mono">([^<]+)</td>', r.content.decode()).group(1)
        self.assertTrue(u.check_password(pw))
        # Confirm cannot be replayed.
        self.client.post(reverse('import_users'), {'action': 'confirm'})
        self.assertEqual(User.objects.filter(username='22520001').count(), 1)

    def test_csv_and_forced_password_change(self):
        self.client.force_login(self.admin)
        f = SimpleUploadedFile('ds.csv', 'username;email\nmoi;moi@x.vn\n'.encode('utf-8'))
        self.client.post(reverse('import_users'), {'action': 'preview', 'file': f, 'course': self.c.pk})
        self.client.post(reverse('import_users'), {'action': 'confirm'})
        moi = User.objects.get(username='moi')
        self.client.force_login(moi)
        self.assertRedirects(self.client.get('/'), reverse('password_change'))
        self.client.post(reverse('password_change'), {
            'old_password': 'x', 'new_password1': 'y', 'new_password2': 'y'})  # wrong: stays flagged
        moi.refresh_from_db()
        self.assertTrue(moi.flags.must_change_password)
        moi.set_password('Mat-khau-rieng-2026')
        moi.save()
        self.client.force_login(moi)
        AccountFlag.objects.filter(user=moi).update(must_change_password=False)
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_rejects_non_spreadsheet(self):
        self.client.force_login(self.admin)
        r = self.client.post(reverse('import_users'), {
            'action': 'preview', 'file': SimpleUploadedFile('ds.xlsx', b'not a zip')})
        self.assertContains(r, 'không hợp lệ')


class NameOrderTests(TestCase):
    def test_vietnamese_full_name(self):
        u = User(first_name='An', last_name='Nguyễn Văn')
        self.assertEqual(u.get_full_name(), 'Nguyễn Văn An')
