import os
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-change-me-notify-app-insecure-key-32chars")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,.onrender.com,.railway.app").split(",") if h.strip()]
INSTALLED_APPS = ["django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles", "corsheaders", "rest_framework", "rest_framework_simplejwt", "accounts", "alerts", "delivery"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "whitenoise.middleware.WhiteNoiseMiddleware", "corsheaders.middleware.CorsMiddleware", "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware", "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware"]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [], "APP_DIRS": True, "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages"]}}]
WSGI_APPLICATION = "config.wsgi.application"
if os.environ.get("DATABASE_URL"):
    import dj_database_url
    DATABASES = {"default": dj_database_url.config(conn_max_age=600, ssl_require=os.environ.get("DB_SSL", "0") == "1")}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
AUTH_PASSWORD_VALIDATORS = [{"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"}, {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"}, {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"}, {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"}]
LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English"), ("ta", "Tamil")]
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {"staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CORS_ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,https://samdaniel05.github.io").split(",") if o.strip()]
CORS_ALLOW_CREDENTIALS = True
REST_FRAMEWORK = {"DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",), "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",)}
SIMPLE_JWT = {"ACCESS_TOKEN_LIFETIME": timedelta(minutes=60), "REFRESH_TOKEN_LIFETIME": timedelta(days=7), "ROTATE_REFRESH_TOKENS": True}
MAGIC_LINK_TTL_MINUTES = 20
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@notify.app")
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
