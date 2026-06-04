from __future__ import annotations

import hashlib
import logging

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

_GEOCODE_URL = f"{settings.ORS_BASE_URL}/geocode/search"


class GeocodingError(Exception):
    """Raised when an address cannot be resolved to coordinates."""


def geocode_address(address: str) -> tuple[float, float]:

    cache_key = "geocode:" + hashlib.md5(address.lower().strip().encode()).hexdigest()
    cached = cache.get(cache_key)
    if cached is not None:
        logger.debug("Geocode cache hit: %s", address)
        return cached

    result = _call_ors_geocode(address)
    cache.set(cache_key, result, timeout=settings.GEOCODE_CACHE_TTL)
    logger.debug("Geocoded '%s' → %s", address, result)
    return result


def _call_ors_geocode(address: str) -> tuple[float, float]:
    if not settings.ORS_API_KEY:
        raise GeocodingError(
            "ORS_API_KEY is not configured. "
            "Sign up at https://openrouteservice.org and add the key to your .env file."
        )

    params = {
        "api_key": settings.ORS_API_KEY,
        "text": address,
        "boundary.country": "US",
        "size": 1,
    }

    try:
        resp = requests.get(
            _GEOCODE_URL,
            params=params,
            timeout=settings.ORS_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code
        if status == 401:
            raise GeocodingError("Invalid ORS API key. Check ORS_API_KEY in your .env file.") from exc
        if status == 403:
            raise GeocodingError("ORS API quota exceeded.") from exc
        raise GeocodingError(f"ORS geocoding error {status} for '{address}'") from exc
    except requests.exceptions.RequestException as exc:
        raise GeocodingError(f"ORS geocoding network error for '{address}': {exc}") from exc

    data = resp.json()
    features = data.get("features", [])
    if not features:
        raise GeocodingError(
            f"Could not find '{address}' in the USA. "
            "Try a more specific address, e.g. 'Chicago, IL' or 'Austin, TX'."
        )

    coords = features[0]["geometry"]["coordinates"]  # [lng, lat]
    return (coords[1], coords[0])  # return as (lat, lng)
