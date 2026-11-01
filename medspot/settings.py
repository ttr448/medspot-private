# medspot/settings.py
"""
Django settings for medspot project.
This file uses django-environ to load DB credentials from a .env file.
"""

import os
from pathlib import Path
import environ
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

SECRET_KEY = env("SECRET_KEY", default="unsafe-secret-for-dev")
DEBUG = env.bool("DEBUG", default=True)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["127.0.0.1", "localhost"])

# Google Maps JavaScript API key is optional during local development.
# Add it to the local .env file; do not commit the key to Git.
GOOGLE_MAPS_API_KEY = env("GOOGLE_MAPS_API_KEY", default="")

INSTALLED_APPS = [
    # default Django apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # local apps (use AppConfig paths if you prefer)
    "users",
    "pharmacies",
    "medicines",
    "inventory",
    "alerts",
    'widget_tweaks'
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

ROOT_URLCONF = "medspot.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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

WSGI_APPLICATION = "medspot.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD", default=""),
        "HOST": env("DB_HOST", default="localhost"),
        "PORT": env("DB_PORT", default="3306"),
        "OPTIONS": {"init_command": "SET sql_mode='STRICT_TRANS_TABLES'"},
    }
}

AUTH_USER_MODEL = "users.CustomUser"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Authentication URLs (Using named URL routes for safety)
LOGIN_URL = "users:login"
LOGIN_REDIRECT_URL = "users:patient_search"  # Redirect path after successful login
LOGOUT_REDIRECT_URL = "users:login"          # Redirect path after logout

# Session configuration
SESSION_COOKIE_AGE = 30 * 60            # 1800 seconds (30 minutes)
SESSION_SAVE_EVERY_REQUEST = True       # Refresh expiry on each request (sliding window)
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
