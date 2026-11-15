from django.apps import AppConfig


class CoursesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'courses'
    verbose_name = 'Học tập'

    def ready(self):
        from django.contrib.auth import get_user_model

        def get_full_name(user):
            # Vietnamese order: family name first ("Nguyễn Văn An").
            return f'{user.last_name} {user.first_name}'.strip()

        get_user_model().get_full_name = get_full_name
