"""
Django settings for config project.
"""

from datetime import timedelta
from pathlib import Path
import sys
import environ
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

# Required behind Render's HTTPS proxy so request.is_secure() and CSRF work correctly
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
# The content value of Search Console's HTML-tag verification (URL-prefix property); set it blank to drop the tag.
GOOGLE_SITE_VERIFICATION = env("GOOGLE_SITE_VERIFICATION", default="FqUC-GbcN9zVyQBOOH2eb2M4YhRqEE5uFOQ9EWCXAD0")
if not DEBUG:
    SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'cloudinary_storage',
    'axes',
    'cloudinary',

    # Third-party
    "django_ckeditor_5",

    # Project apps
    "apps.subjects",
    "apps.lessons",
    "apps.accounts",
    "apps.questions",
    "apps.quizzes",
    "apps.progress",
]

CKEDITOR_5_CONFIGS = {
    "extends": {
        "toolbar": [
            "heading", "|",
            "bold", "italic", "link", "|",
            "fontColor", "fontBackgroundColor", "|",
            "alignment", "|",
            "imageUpload", "bulletedList", "numberedList", "blockQuote", "|",
            "code", "codeBlock", "|",
            "insertTable", "|",
            "undo", "redo",
        ],
        "alignment": {
            "options": ["left", "center", "right", "justify"],
        },
        "fontColor": {
            "colors": [
                {"color": "#ffffff", "label": "White"},
                {"color": "#3ddc84", "label": "Green"},
                {"color": "#f4c430", "label": "Amber"},
                {"color": "#ff6b6b", "label": "Red"},
                {"color": "#5ea8ff", "label": "Blue"},
                {"color": "#c792ea", "label": "Purple"},
            ],
            "columns": 6,
        },
        "fontBackgroundColor": {
            "colors": [
                {"color": "#10261a", "label": "Dark green"},
                {"color": "#2a1414", "label": "Dark red"},
                {"color": "#1a222d", "label": "Slate"},
            ],
            "columns": 3,
        },
        "codeBlock": {
            "languages": [
                {"language": "plaintext", "label": "Pseudocode"},
                {"language": "c", "label": "C"},
                {"language": "pascal", "label": "Pascal"},
                {"language": "python", "label": "Python"},
                {"language": "sql", "label": "SQL"},
            ],
        },
        "table": {
            "contentToolbar": [
                "tableColumn", "tableRow", "mergeTableCells",
                "tableProperties", "tableCellProperties",
            ],
        },
    },
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # must come right after SecurityMiddleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'axes.middleware.AxesMiddleware',  # keep last
]

# Brute-force protection for /accounts/login/ and /admin/login/: 5 failures lock that username for 15 minutes.
# Locking by username only (not IP) because a school shares one IP and the proxy chain on Render is unverified;
# switch to [["ip_address", "username"]] with AXES_IPWARE_PROXY_COUNT once the real client IP is trustworthy.
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_LOCKOUT_PARAMETERS = ["username"]
AXES_RESET_ON_SUCCESS = True
SILENCED_SYSTEM_CHECKS = ['axes.W006']  # username-only lockout is deliberate, see above

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.site_verification',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database

# DATABASE_URL points at Supabase (use the Session pooler string from Project Settings > Database).
DATABASES = {
    "default": env.db("DATABASE_URL"),
}
# Supabase only accepts SSL connections; set DB_SSLMODE=disable for a local Postgres without SSL.
DATABASES["default"]["OPTIONS"] = {"sslmode": env("DB_SSLMODE", default="require")}
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
if str(DATABASES["default"].get("PORT")) == "6543":
    # Supabase's transaction pooler can't hold persistent connections or server-side cursors.
    DATABASES["default"]["CONN_MAX_AGE"] = 0
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
else:
    DATABASES["default"]["CONN_MAX_AGE"] = 600

if "test" in sys.argv[:2]:
    # Never create test databases on the shared Supabase server.
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Internationalization

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/Jamaica'
USE_I18N = True
USE_TZ = True


# Static files

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
# settings.py

STORAGES = {
    "default": {
        "BACKEND": "apps.core.storage.SeekSafeCloudinaryStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

if "test" in sys.argv[:2]:
    # The default hasher is deliberately slow; tests create many users.
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    STORAGES["staticfiles"] = {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}

#admin panel customizations
CKEDITOR_5_FILE_STORAGE = "apps.core.storage.SeekSafeCloudinaryStorage"

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

#Cloudinary settings

CLOUDINARY_STORAGE = {
    "CLOUD_NAME": env("CLOUDINARY_CLOUD_NAME"),
    "API_KEY": env("CLOUDINARY_API_KEY"),
    "API_SECRET": env("CLOUDINARY_API_SECRET"),
}

# Email defaults to the console backend locally; configure SMTP through the environment in production.
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
if not DEBUG and "test" not in sys.argv[:2] and EMAIL_BACKEND.endswith("console.EmailBackend"):
    # Otherwise password-reset emails only reach the server log.
    raise ImproperlyConfigured("Set EMAIL_BACKEND (and the EMAIL_* SMTP settings) when DEBUG is off.")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@cxcstudy.com")
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)

# 20 MB, up from Django's 2.5 MB default
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024 

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}