"""The signed-in user's own profile and account settings."""
from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import redirect, render

from .models import Assignment, Enrollment, Submission

User = get_user_model()


class ProfileForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('label_suffix', '')
        super().__init__(*args, **kwargs)

    class Meta:
        model = User
        fields = ['last_name', 'first_name', 'email']
        labels = {'last_name': 'Họ và tên đệm', 'first_name': 'Tên', 'email': 'Email'}

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if email and User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Email này đã được tài khoản khác sử dụng.')
        return email


@login_required
def profile(request):
    user = request.user
    enrollments = (Enrollment.objects.filter(user=user).select_related('course')
                   .annotate(n_assign=Count('course__assignments', distinct=True))
                   .order_by('course__code'))
    submitted = dict(Submission.objects.filter(student=user)
                     .values_list('assignment__course_id').annotate(n=Count('assignment', distinct=True)))
    students = dict(Enrollment.objects.filter(course__in=[e.course_id for e in enrollments], role=Enrollment.STUDENT)
                    .values_list('course_id').annotate(n=Count('id')))
    rows = [{'e': e, 'submitted': submitted.get(e.course_id, 0), 'students': students.get(e.course_id, 0)}
            for e in enrollments]
    recent = (Submission.objects.filter(student=user).select_related('assignment__course')
              .order_by('-submitted_at')[:8])
    graded = Submission.objects.filter(student=user, score__isnull=False).count()
    return render(request, 'account/profile.html', {
        'rows': rows, 'recent': recent,
        'n_courses': len(rows), 'n_submissions': Submission.objects.filter(student=user).count(),
        'n_graded': graded,
    })


@login_required
def settings_view(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Đã lưu thông tin cá nhân.')
        return redirect('profile')
    return render(request, 'account/settings.html', {'form': form})
