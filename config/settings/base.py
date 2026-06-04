from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())

# ── Application definition ────────────────────────────────────────────────────

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
]

LOCAL_APPS = [
    "apps.stations",
    "apps.routes",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "config.wsgi.application"

# ── Auth ──────────────────────────────────────────────────────────────────────

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ── Internationalisation ──────────────────────────────────────────────────────

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ── Static files ──────────────────────────────────────────────────────────────

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Django REST Framework ─────────────────────────────────────────────────────

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "200/hour",
    },
    "EXCEPTION_HANDLER": "apps.routes.exceptions.custom_exception_handler",
}

# ── drf-spectacular (OpenAPI docs) ────────────────────────────────────────────

SPECTACULAR_SETTINGS = {
    "TITLE": "Fuel Route Optimizer API",
    "DESCRIPTION": (
        "Given a US origin and destination, returns the optimal route with "
        "cost-effective fuel stops based on live truck-stop prices."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# ── CORS ──────────────────────────────────────────────────────────────────────

CORS_ALLOW_ALL_ORIGINS = DEBUG  # Tighten in production via CORS_ALLOWED_ORIGINS

# ── OpenRouteService (geocoding only) ────────────────────────────────────────
# ORS is used ONLY for geocoding origin/destination (city name → coordinates).
# Routing is handled by OSRM below — no API key, no rate limit.

ORS_API_KEY = config("ORS_API_KEY", default="")
ORS_BASE_URL = "https://api.openrouteservice.org"
ORS_TIMEOUT_SECONDS = 30
ORS_MAX_RETRIES = 3

# ── OSRM routing (free, no API key, no rate limit) ────────────────────────────
# Public demo server. For production, self-host: https://project-osrm.org

OSRM_BASE_URL = config("OSRM_BASE_URL", default="https://router.project-osrm.org")

# ── Vehicle / route constants ─────────────────────────────────────────────────

VEHICLE_MAX_RANGE_MILES = config("VEHICLE_MAX_RANGE_MILES", default=500, cast=int)
VEHICLE_MPG = config("VEHICLE_MPG", default=10, cast=int)
# Corridor width around the route in which we look for fuel stations
ROUTE_CORRIDOR_MILES = config("ROUTE_CORRIDOR_MILES", default=30, cast=int)
# Simplify route to one waypoint every N miles before spatial search.
# Reduces 10 000+ OSRM points to ~560 for a 2 800-mile trip (21x fewer).
ROUTE_SIMPLIFY_SPACING_MILES = config("ROUTE_SIMPLIFY_SPACING_MILES", default=5, cast=int)

# ── Caching TTLs ──────────────────────────────────────────────────────────────

ROUTE_CACHE_TTL = config("ROUTE_CACHE_TTL_SECONDS", default=86_400, cast=int)   # 24 h
GEOCODE_CACHE_TTL = config("GEOCODE_CACHE_TTL_SECONDS", default=2_592_000, cast=int)  # 30 days
