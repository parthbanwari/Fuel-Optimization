from .base import *  # noqa: F401, F403

DEBUG = True

# ── SQLite for frictionless local development ─────────────────────────────────

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
    }
}

# ── In-memory cache (no Redis needed for quick local runs) ───────────────────
# Switch to the Redis block below once you have Redis running locally.

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# ── Uncomment to use Redis locally ───────────────────────────────────────────
# from decouple import config as _config
# CACHES = {
#     "default": {
#         "BACKEND": "django_redis.cache.RedisCache",
#         "LOCATION": _config("REDIS_URL", default="redis://localhost:6379/0"),
#         "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
#     }
# }

CORS_ALLOW_ALL_ORIGINS = True
