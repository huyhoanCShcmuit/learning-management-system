import os

from django import forms

from .models import Assignment, Submission
from .security import BLOCKED_EXT, content_matches


class SubmissionForm(forms.Form):
    file = forms.FileField(label='Chọn file')

    def __init__(self, *args, assignment, **kwargs):
        kwargs.setdefault('label_suffix', '')
        super().__init__(*args, **kwargs)
        self.assignment = assignment
        self.fields['file'].help_text = (
            f'Định dạng: {assignment.allowed_display} · tối đa {assignment.max_size_mb} MB'
        )

    def clean_file(self):
        f = self.cleaned_data['file']
        ext = os.path.splitext(f.name)[1].lower().lstrip('.')
        if not self.assignment.accepts(ext):
            raise forms.ValidationError(f'Không nhận file .{ext}' if ext else 'File cần có đuôi (ví dụ .pdf).')
        if f.size > self.assignment.max_size_mb * 1024 * 1024:
            raise forms.ValidationError(f'File vượt quá {self.assignment.max_size_mb} MB')
        if f.size == 0:
            raise forms.ValidationError('File rỗng.')
        if not content_matches(f, ext):
            raise forms.ValidationError(f'Nội dung file không đúng định dạng .{ext}')
        return f


class GradeForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ['score', 'feedback']
        widgets = {'feedback': forms.Textarea(attrs={'rows': 2})}

    def clean_score(self):
        score = self.cleaned_data['score']
        if score is not None and not (0 <= score <= self.instance.assignment.max_score):
            raise forms.ValidationError(f'Điểm phải từ 0 đến {self.instance.assignment.max_score}')
        return score


class DateTimeInput(forms.DateTimeInput):
    input_type = 'datetime-local'

    def format_value(self, value):
        if hasattr(value, 'strftime'):
            return value.strftime('%Y-%m-%dT%H:%M')
        return value


class AssignmentForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('label_suffix', '')
        super().__init__(*args, **kwargs)

    class Meta:
        model = Assignment
        fields = ['title', 'description', 'open_at', 'due_at', 'cutoff_at',
                  'allowed_ext', 'max_size_mb', 'max_score']
        widgets = {
            'open_at': DateTimeInput(),
            'due_at': DateTimeInput(),
            'cutoff_at': DateTimeInput(),
            'description': forms.Textarea(attrs={'rows': 4}),
        }

    def clean_max_size_mb(self):
        mb = self.cleaned_data['max_size_mb']
        if not 1 <= mb <= 60:  # Caddy rejects bodies over 60 MB
            raise forms.ValidationError('Dung lượng phải từ 1 đến 60 MB.')
        return mb

    def clean_allowed_ext(self):
        exts = [e.strip().lower().lstrip('.') for e in self.cleaned_data['allowed_ext'].split(',') if e.strip()]
        bad = [e for e in exts if e in BLOCKED_EXT]
        if bad:
            raise forms.ValidationError(f'Không được cho phép: {", ".join(bad)}')
        return ','.join(exts)

    def clean(self):
        data = super().clean()
        open_at, due_at, cutoff_at = data.get('open_at'), data.get('due_at'), data.get('cutoff_at')
        if open_at and due_at and due_at < open_at:
            self.add_error('due_at', 'Hạn nộp phải sau thời điểm mở.')
        if due_at and cutoff_at and cutoff_at < due_at:
            self.add_error('cutoff_at', 'Khoá nộp phải sau hạn nộp.')
        return data
