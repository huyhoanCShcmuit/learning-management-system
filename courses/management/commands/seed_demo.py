from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from courses.models import Assignment, Course, Enrollment

PASSWORD = 'demo1234'  # demo only


class Command(BaseCommand):
    help = 'Tạo dữ liệu mẫu: admin, 1 giáo viên, 3 học sinh, 2 khoá, vài bài tập.'

    def handle(self, *args, **opts):
        def user(username, first, last, superuser=False):
            u, created = User.objects.get_or_create(
                username=username, defaults={'first_name': first, 'last_name': last})
            if created:
                u.set_password(PASSWORD)
                u.is_superuser = u.is_staff = superuser
                u.save()
            return u

        user('admin', 'Quản', 'Trị', superuser=True)
        gv = user('gv1', 'Văn A', 'Nguyễn')
        hs = [user('hs1', 'Thị B', 'Trần'), user('hs2', 'Văn C', 'Lê'), user('hs3', 'Thị D', 'Phạm')]

        now = timezone.now()
        web, _ = Course.objects.get_or_create(
            code='WEB101', defaults={'name': 'Lập trình Web', 'description': 'Học kỳ 1, 2026-2027'})
        ai, _ = Course.objects.get_or_create(
            code='AI201', defaults={'name': 'Nhập môn Trí tuệ nhân tạo'})

        for c in (web, ai):
            Enrollment.objects.get_or_create(user=gv, course=c, defaults={'role': Enrollment.TEACHER})
        for s in hs:
            Enrollment.objects.get_or_create(user=s, course=web)
        Enrollment.objects.get_or_create(user=hs[0], course=ai)

        if not web.assignments.exists():
            Assignment.objects.create(
                course=web, title='Bài 1: Trang HTML cá nhân',
                description='Nộp file zip chứa index.html và CSS.',
                open_at=now - timedelta(days=7), due_at=now - timedelta(days=1),
                cutoff_at=now + timedelta(days=2), allowed_ext='zip')
            Assignment.objects.create(
                course=web, title='Bài 2: Form đăng ký',
                description='Nộp báo cáo PDF và mã nguồn zip.',
                open_at=now - timedelta(days=1), due_at=now + timedelta(days=5),
                allowed_ext='pdf,zip')
            Assignment.objects.create(
                course=web, title='Bài 0: Khảo sát đầu kỳ',
                open_at=now - timedelta(days=20), due_at=now - timedelta(days=10),
                allowed_ext='pdf,docx')
        if not ai.assignments.exists():
            Assignment.objects.create(
                course=ai, title='Bài 1: Tìm kiếm BFS/DFS',
                open_at=now, due_at=now + timedelta(days=10), allowed_ext='pdf,zip,py')

        self.stdout.write(self.style.SUCCESS(
            f'Xong. Tài khoản: admin / gv1 / hs1 / hs2 / hs3, mật khẩu: {PASSWORD}'))
