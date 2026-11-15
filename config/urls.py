from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views

from courses.models import AccountFlag
from django.templatetags.static import static
from django.urls import include, path
from django.views.generic import RedirectView, TemplateView



class PasswordChange(auth_views.PasswordChangeView):
    """Clears the 'must change password' flag once the user sets their own."""
    def form_valid(self, form):
        resp = super().form_valid(form)
        AccountFlag.objects.filter(user=self.request.user).update(must_change_password=False)
        return resp


admin.site.site_header = 'Quản trị · Learning Management System'
admin.site.site_title = 'Quản trị · Learning Management System'
admin.site.index_title = 'Quản lý người dùng, khoá học, bài tập'

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path('login/', auth_views.LoginView.as_view(redirect_authenticated_user=True), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('password/', PasswordChange.as_view(), name='password_change'),
    path('password/done/', auth_views.PasswordChangeDoneView.as_view(), name='password_change_done'),
    path('help/', TemplateView.as_view(template_name='pages/help.html'), name='help'),
    path('privacy/', TemplateView.as_view(template_name='pages/privacy.html'), name='privacy'),
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain')),
    path('favicon.ico', RedirectView.as_view(url=static('courses/favicon.svg'), permanent=True)),
    path('', include('courses.urls')),
]
