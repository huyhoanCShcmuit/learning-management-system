from django.contrib import admin

from .models import AccountFlag, Assignment, Course, Enrollment, Submission


class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 1
    autocomplete_fields = ['user']


class AssignmentInline(admin.TabularInline):
    model = Assignment
    extra = 0
    fields = ['title', 'open_at', 'due_at', 'cutoff_at']


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['code', 'name']
    search_fields = ['code', 'name']
    inlines = [EnrollmentInline, AssignmentInline]


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ['user', 'course', 'role', 'enrolled_at']
    list_filter = ['course', 'role']
    search_fields = ['user__username', 'user__first_name', 'user__last_name']


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'open_at', 'due_at', 'cutoff_at']
    list_filter = ['course']


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ['assignment', 'student', 'submitted_at', 'is_late', 'score']
    list_filter = ['assignment__course', 'is_late']
    readonly_fields = ['created_at', 'submitted_at']



@admin.register(AccountFlag)
class AccountFlagAdmin(admin.ModelAdmin):
    list_display = ['user', 'must_change_password', 'created_by_import']
    list_filter = ['must_change_password', 'created_by_import']
    search_fields = ['user__username']
