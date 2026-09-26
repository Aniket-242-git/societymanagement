"""
Django settings for the Society Management System.

Architecture:
  - API/     : DRF backend (JWT auth, versioned REST endpoints /api/v1/...)
  - UI/      : Django server-rendered frontend (Bootstrap + jQuery/AJAX)
"""
import os
from datetime import timedelta
from pathlib import Path

from API.config.env import load_dotenv

load_dotenv()  # project-root .env -> os.environ (existing vars win)

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # project root


def env(key, default=""):
    return os.environ.get(key, default)


def env_int(key, default):
    try:
        return int(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


# ENV=dev  -> SQLite (zero config).  ENV=prod -> MySQL (shared hosting C plan).
APP_ENV = env("ENV", "dev").lower()

SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-insecure-key-change-in-production")
DEBUG = env("DJANGO_DEBUG", "1" if APP_ENV != "prod" else "0") == "1"
ALLOWED_HOSTS = [h.strip() for h in env("DJANGO_ALLOWED_HOSTS", "*").split(",") if h.strip()] or ["*"]

SITE_NAME = env("SITE_NAME", "Green Valley Society")
PAGE_SIZE = env_int("PAGE_SIZE", 10)

# ---------------------------------------------------------------- apps
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third party
    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",
    # local API apps
    "API.apps.core",
    "API.apps.accounts",
    "API.apps.flats",
    "API.apps.announcements",
    "API.apps.issues",
    "API.apps.payments",
    "API.apps.expenses",
    "API.apps.reports",
    # UI app (server rendered pages)
    "UI",
]

AUTHENTICATION_BACKENDS = [
    "API.apps.accounts.backends.PhoneOrUsernameBackend",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "API.config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "UI" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "API.config.wsgi.application"
ASGI_APPLICATION = "API.config.asgi.application"

# ---------------------------------------------------------------- database
# ENV=prod  -> MySQL   (shared hosting "C plan": create DB/user in cPanel,
#                       fill DB_* vars in .env)
# ENV=dev   -> SQLite  (default, zero config)
# DB_ENGINE (sqlite|mysql) overrides the ENV-based choice when set.
_db_engine = env("DB_ENGINE", "").lower() or ("mysql" if APP_ENV == "prod" else "sqlite")

if _db_engine == "mysql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": env("DB_NAME", "society_db"),
            "USER": env("DB_USER", ""),
            "PASSWORD": env("DB_PASSWORD", ""),
            "HOST": env("DB_HOST", "localhost"),
            "PORT": env("DB_PORT", "3306"),
            "OPTIONS": {"charset": "utf8mb4"},
        }
    }
elif _db_engine == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DB_NAME", "society_db"),
            "USER": env("DB_USER", "postgres"),
            "PASSWORD": env("DB_PASSWORD", ""),
            "HOST": env("DB_HOST", "localhost"),
            "PORT": env("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "accounts.User"

# ---------------------------------------------------------------- auth / security
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------- DRF + JWT
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "API.apps.core.pagination.StandardPagination",
    "PAGE_SIZE": PAGE_SIZE,
    "DEFAULT_ORDERING": ["-created_at"],
    "EXCEPTION_HANDLER": "API.apps.core.exceptions.api_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": ("rest_framework.throttling.AnonRateThrottle",),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "login": "10/min",          # brute-force protection on token endpoints
        "payment_submit": "20/min", # abuse protection on payment submissions
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env_int("JWT_ACCESS_MINUTES", 60)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env_int("JWT_REFRESH_DAYS", 7)),
    "ROTATE_REFRESH_TOKENS": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Society Management API",
    "DESCRIPTION": "API-first housing society management system (flats, services, "
                   "payments, issues, expenses, announcements).",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# ---------------------------------------------------------------- i18n
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------- static / media
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "UI" / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------- upload limits
MAX_UPLOAD_SIZE = env_int("MAX_UPLOAD_SIZE_MB", 5) * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"]

LOGIN_URL = "/login/"

# ---------------------------------------------------------------- proxy / ssl (shared hosting)
if env("BEHIND_PROXY", "0") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = not DEBUG
    CSRF_COOKIE_SECURE = not DEBUG
