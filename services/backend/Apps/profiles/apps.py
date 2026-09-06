from django.apps import AppConfig


class ProfilesConfig(AppConfig):
    name = 'Apps.profiles'

    def ready(self):
        from . import signals  # noqa: F401
