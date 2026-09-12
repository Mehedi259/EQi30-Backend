from datetime import timedelta
from pathlib import Path

import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False)
)
environ.Env.read_env(BASE_DIR / ".env")

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env(
    "SECRET_KEY",
    default="django-insecure-i1jw%i7yq*2b1o=b*&x%y2m=q)^2i46vr-nro-^2k%u=#hn9^5",
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env("DEBUG")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]
THIRD_PARTY_APPS = [
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
]

LOCAL_APPS = [
    'Apps.users',
    'Apps.profiles',
    'Apps.abilities',
    'Apps.journey',
    'Apps.learning',
    'Apps.progress',
    'Apps.resources',
    'Apps.meditation',
    'Apps.yoga',
    'Apps.notifications',
    'Apps.subscriptions',
    'Apps.support',
    'Apps.feedback',
    'Apps.legal',
    'Apps.ai',
]
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Authentication
AUTH_USER_MODEL = "users.User"

# Password validation
# https://docs.djangoproject.com/en/6.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static & media files

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Email
# https://docs.djangoproject.com/en/6.1/topics/email/#topic-email-configuration

EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="").strip()
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="").strip()
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="no-reply@eqi30.app").strip()


# ---------------------------------------------------------------------------
# CORS (django-cors-headers)
# ---------------------------------------------------------------------------

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])


# ---------------------------------------------------------------------------
# REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_SCHEMA_CLASS": "core.schema.CategorizedAutoSchema",
}


# ---------------------------------------------------------------------------
# Simple JWT
# ---------------------------------------------------------------------------
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}


# ---------------------------------------------------------------------------
# drf-spectacular (Swagger / OpenAPI 3.0)
# ---------------------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    "TITLE": "EQi30 API - Made by Mehedi Hasan Mridul",
    "DESCRIPTION": "REST API documentation for the EQi30 backend.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,  # hide the raw schema endpoint from the docs list
    "COMPONENT_SPLIT_REQUEST": True,
    # Declaring tags keeps Swagger UI categories consistently ordered.
    "TAGS": [
        {"name": "Authentication", "description": "Registration, login, tokens, and password management."},
        {"name": "Profile & Account", "description": "User profile and account settings."},
        {"name": "Onboarding", "description": "Anonymous onboarding and assessment flow."},
        {"name": "Abilities", "description": "Emotional-intelligence ability catalog."},
        {"name": "Journey", "description": "Personalized guided journey."},
        {"name": "Learning", "description": "Daily learning sessions, reflections, and check-ins."},
        {"name": "Progress", "description": "Dashboard and progress tracking."},
        {"name": "Resources", "description": "Resource library and favorites."},
        {"name": "Notifications", "description": "Reminder preferences."},
        {"name": "Subscriptions", "description": "Subscription plans and status."},
        {"name": "Support", "description": "Help and frequently asked questions."},
        {"name": "Feedback", "description": "User feedback and support requests."},
        {"name": "Legal", "description": "Privacy policy and terms of service."},
    ],
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
        "displayOperationId": True,
    },
}


# ---------------------------------------------------------------------------
# EQi30 business rules
# ---------------------------------------------------------------------------
# Anonymous onboarding data is deleted if the user does not register in time.
ANONYMOUS_SESSION_TTL_MINUTES = env.int("ANONYMOUS_SESSION_TTL_MINUTES", default=10)
# Password-reset OTP lifetime.
PASSWORD_RESET_OTP_TTL_MINUTES = env.int("PASSWORD_RESET_OTP_TTL_MINUTES", default=10)
# Confirmed challenge length (the 60-day Figma screen is NOT confirmed yet).
JOURNEY_TOTAL_DAYS = env.int("JOURNEY_TOTAL_DAYS", default=30)
