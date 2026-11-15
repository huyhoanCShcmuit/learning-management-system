import os
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Course(models.Model):
    code = models.CharField('Mã khoá', max_length=20, unique=True)
    name = models.CharField('Tên khoá', max_length=200)
    description = models.TextField('Mô tả', blank=True)
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through='Enrollment', related_name='courses'
    )

    class Meta:
        ordering = ['code']
        verbose_name = 'Khoá học'
        verbose_name_plural = 'Khoá học'

    def __str__(self):
        return f'{self.code} - {self.name}'

    @property
    def color(self):
        """Stable colour slot (c0..c5) for the course banner."""
        return f'c{sum(map(ord, self.code)) % 6}'


class Enrollment(models.Model):
    STUDENT = 'student'
    TEACHER = 'teacher'
    ROLES = [(STUDENT, 'Học sinh'), (TEACHER, 'Giáo viên')]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    role = models.CharField('Vai trò', max_length=10, choices=ROLES, default=STUDENT)
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'course')
        verbose_name = 'Ghi danh'
        verbose_name_plural = 'Ghi danh'

    def __str__(self):
        return f'{self.user} @ {self.course.code} ({self.get_role_display()})'


class Assignment(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='assignments')
    title = models.CharField('Tiêu đề', max_length=200)
    description = models.TextField('Đề bài', blank=True)
    open_at = models.DateTimeField('Mở nộp', default=timezone.now)
    due_at = models.DateTimeField('Hạn nộp')
    cutoff_at = models.DateTimeField(
        'Khoá nộp', null=True, blank=True,
        help_text='Sau hạn nộp vẫn nhận bài trễ đến mốc này. Để trống = không nhận bài trễ.',
    )
    max_attempts = models.PositiveIntegerField('Số lần nộp tối đa', default=3)
    allowed_ext = models.CharField(
        'Đuôi file cho phép', max_length=300, blank=True, default='',
        help_text='Để trống = nhận mọi định dạng (trừ file thực thi). '
                  'Hoặc liệt kê, cách nhau bằng dấu phẩy: pdf,docx,zip',
    )
    max_size_mb = models.PositiveIntegerField('Dung lượng tối đa (MB)', default=50)
    max_score = models.DecimalField('Điểm tối đa', max_digits=5, decimal_places=2, default=10)

    class Meta:
        ordering = ['due_at']
        verbose_name = 'Bài tập'
        verbose_name_plural = 'Bài tập'

    def __str__(self):
        return f'{self.course.code}: {self.title}'

    @property
    def close_at(self):
        return self.cutoff_at or self.due_at

    def status(self, now=None):
        now = now or timezone.now()
        if now < self.open_at:
            return 'not_open'
        if now <= self.due_at:
            return 'open'
        if now <= self.close_at:
            return 'late'
        return 'closed'

    def allowed_ext_list(self):
        return [e.strip().lower().lstrip('.') for e in self.allowed_ext.split(',') if e.strip()]

    def accepts(self, ext):
        from .security import BLOCKED_EXT
        if ext in BLOCKED_EXT:
            return False
        allowed = self.allowed_ext_list()
        return not allowed or ext in allowed

    @property
    def allowed_display(self):
        return ', '.join(self.allowed_ext_list()) or 'Mọi định dạng'


def submission_path(instance, filename):
    # Never trust the client's file name on disk.
    ext = os.path.splitext(filename)[1].lower()
    return f'submissions/{instance.assignment_id}/{instance.student_id}/{uuid.uuid4().hex}{ext}'


class Submission(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    attempt_no = models.PositiveIntegerField('Lần nộp')
    file = models.FileField(upload_to=submission_path)
    original_name = models.CharField(max_length=255)
    submitted_at = models.DateTimeField(default=timezone.now)
    is_late = models.BooleanField('Trễ hạn', default=False)

    score = models.DecimalField('Điểm', max_digits=5, decimal_places=2, null=True, blank=True)
    feedback = models.TextField('Nhận xét', blank=True)
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='graded_submissions',
    )
    graded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-submitted_at']
        unique_together = ('assignment', 'student', 'attempt_no')
        verbose_name = 'Bài nộp'
        verbose_name_plural = 'Bài nộp'

    def __str__(self):
        return f'{self.student} - {self.assignment} (lần {self.attempt_no})'


class AccountFlag(models.Model):
    """Per-user flags that don't belong on the auth User model."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='flags')
    must_change_password = models.BooleanField('Bắt buộc đổi mật khẩu', default=False)
    created_by_import = models.BooleanField('Tạo từ file nhập', default=False)

    class Meta:
        verbose_name = 'Trạng thái tài khoản'
        verbose_name_plural = 'Trạng thái tài khoản'
