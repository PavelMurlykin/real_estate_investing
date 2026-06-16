import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


def get_env_list(name, default=''):
    """Return a comma-separated environment variable as a clean list."""
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(',') if item.strip()]


def get_env_int(name, default):
    """Return an integer environment variable with fallback for blank values."""
    value = os.getenv(name)
    if value is None or value.strip() == '':
        return default
    return int(value)


DEBUG = os.getenv('DEBUG', 'False').strip().lower() in (
    '1',
    'true',
    'yes',
    'on',
)
SECRET_KEY = os.getenv('SECRET_KEY', '')

ALLOWED_HOSTS = get_env_list(
    'ALLOWED_HOSTS',
    'localhost,127.0.0.1,192.168.1.175',
)
CSRF_TRUSTED_ORIGINS = get_env_list('CSRF_TRUSTED_ORIGINS')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_bootstrap5',
    'users.apps.UsersConfig',
    'homepage.apps.HomepageConfig',
    'location.apps.LocationConfig',
    'property.apps.PropertyConfig',
    'bank.apps.BankConfig',
    'mortgage.apps.CalculatorConfig',
    'trench_mortgage.apps.TrenchMortgageConfig',
    'customer.apps.CustomerConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'real_estate_investing.urls'

TEMPLATES_DIR = BASE_DIR / 'templates'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [TEMPLATES_DIR],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'users.context_processors.application_roles',
            ],
        },
    },
]

WSGI_APPLICATION = 'real_estate_investing.wsgi.application'
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', ''),
        'USER': os.getenv('DB_USER', ''),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000

AUTH_USER_MODEL = 'users.User'

AUTHENTICATION_BACKENDS = [
    'users.backends.EmailOrPhoneBackend',
]

LOGIN_URL = 'users:login'
LOGIN_REDIRECT_URL = 'homepage:index'
LOGOUT_REDIRECT_URL = 'homepage:index'

EMAIL_BACKEND = os.getenv(
    'EMAIL_BACKEND',
    (
        'django.core.mail.backends.console.EmailBackend'
        if DEBUG
        else 'django.core.mail.backends.smtp.EmailBackend'
    ),
)
EMAIL_HOST = os.getenv('EMAIL_HOST', 'localhost')
EMAIL_PORT = get_env_int('EMAIL_PORT', 25)
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'False').strip().lower() in (
    '1',
    'true',
    'yes',
    'on',
)
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'False').strip().lower() in (
    '1',
    'true',
    'yes',
    'on',
)
DEFAULT_FROM_EMAIL = os.getenv(
    'DEFAULT_FROM_EMAIL',
    'webmaster@localhost',
)
