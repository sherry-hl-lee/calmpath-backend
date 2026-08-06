from collections import OrderedDict, defaultdict, deque
from dataclasses import dataclass
import math
import threading
import time
from typing import Any

import httpx

from app.core.config import CITY_OF_MELBOURNE_STREET_ADDRESSES_URL
from app.schemas.refuge import RefugeAddress


ADDRESS_LOOKUP_RADIUS_M = 200
CACHE_TTL_SECONDS = 600
CACHE_MAX_ENTRIES = 256
MAX_REQUESTS_PER_IP = 30
RATE_LIMIT_WINDOW_SECONDS = 60
MAX_UPSTREAM_CONCURRENCY = 4
UPSTREAM_TIMEOUT_SECONDS = 5
ADDRESS_SOURCE = "City of Melbourne Street Addresses"


class AddressRateLimitExceeded(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__("Address lookup rate limit exceeded")


class AddressUpstreamError(Exception):
    def __init__(self, message: str, retry_after: str | None = None) -> None:
        self.retry_after = retry_after
        super().__init__(message)


@dataclass
class _CacheEntry:
    expires_at: float
    value: RefugeAddress | None


class AddressService:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=UPSTREAM_TIMEOUT_SECONDS)
        self._cache: OrderedDict[tuple[float, float], _CacheEntry] = OrderedDict()
        self._request_times: defaultdict[str, deque[float]] = defaultdict(deque)
        self._cache_lock = threading.Lock()
        self._rate_limit_lock = threading.Lock()
        self._upstream_slots = threading.BoundedSemaphore(MAX_UPSTREAM_CONCURRENCY)

    def find_address(
        self,
        latitude: float,
        longitude: float,
        client_ip: str,
    ) -> RefugeAddress | None:
        now = time.monotonic()
        self._enforce_rate_limit(client_ip, now)
        cache_key = (round(latitude, 5), round(longitude, 5))
        cached, found = self._get_cached(cache_key, now)
        if found:
            return cached

        if not self._upstream_slots.acquire(timeout=UPSTREAM_TIMEOUT_SECONDS):
            raise AddressUpstreamError("City of Melbourne address API is busy")
        try:
            result = self._request_address(latitude, longitude)
        finally:
            self._upstream_slots.release()

        self._set_cached(cache_key, result, time.monotonic())
        return result

    def reset_state(self) -> None:
        with self._cache_lock:
            self._cache.clear()
        with self._rate_limit_lock:
            self._request_times.clear()

    def _request_address(self, latitude: float, longitude: float) -> RefugeAddress | None:
        params = {
            "select": (
                "address_pnt,latitude,longitude,"
                f"distance(geo_point_2d, geom'POINT({longitude} {latitude})') as match_distance_m"
            ),
            "where": f"within_distance(geo_point_2d, geom'POINT({longitude} {latitude})', 200 m)",
            "order_by": f"distance(geo_point_2d, geom'POINT({longitude} {latitude})') asc",
            "limit": 1,
        }
        try:
            response = self._client.get(CITY_OF_MELBOURNE_STREET_ADDRESSES_URL, params=params)
        except httpx.TimeoutException as error:
            raise AddressUpstreamError("City of Melbourne address API timed out") from error
        except httpx.RequestError as error:
            raise AddressUpstreamError("City of Melbourne address API is unavailable") from error

        if response.status_code == 429:
            raise AddressUpstreamError(
                "City of Melbourne address API rate limit reached",
                retry_after=response.headers.get("Retry-After"),
            )
        if response.status_code >= 500:
            raise AddressUpstreamError(
                "City of Melbourne address API returned a server error",
                retry_after=response.headers.get("Retry-After"),
            )
        if response.status_code >= 400:
            raise AddressUpstreamError("City of Melbourne address API rejected the request")

        try:
            payload = response.json()
        except ValueError as error:
            raise AddressUpstreamError("City of Melbourne address API returned invalid JSON") from error

        results = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(results, list):
            raise AddressUpstreamError("City of Melbourne address API returned an invalid response")

        for result in results:
            if not isinstance(result, dict):
                continue
            address = result.get("address_pnt")
            record_latitude = _finite_float(result.get("latitude"), -90, 90)
            record_longitude = _finite_float(result.get("longitude"), -180, 180)
            match_distance = _finite_float(result.get("match_distance_m"), 0, ADDRESS_LOOKUP_RADIUS_M)
            if (
                isinstance(address, str)
                and address.strip()
                and record_latitude is not None
                and record_longitude is not None
                and match_distance is not None
            ):
                return RefugeAddress(
                    address=address.strip(),
                    latitude=record_latitude,
                    longitude=record_longitude,
                    match_distance_m=match_distance,
                    source=ADDRESS_SOURCE,
                )
        return None

    def _enforce_rate_limit(self, client_ip: str, now: float) -> None:
        with self._rate_limit_lock:
            request_times = self._request_times[client_ip]
            cutoff = now - RATE_LIMIT_WINDOW_SECONDS
            while request_times and request_times[0] <= cutoff:
                request_times.popleft()
            if len(request_times) >= MAX_REQUESTS_PER_IP:
                retry_after = max(1, math.ceil(request_times[0] + RATE_LIMIT_WINDOW_SECONDS - now))
                raise AddressRateLimitExceeded(retry_after)
            request_times.append(now)

    def _get_cached(
        self,
        cache_key: tuple[float, float],
        now: float,
    ) -> tuple[RefugeAddress | None, bool]:
        with self._cache_lock:
            entry = self._cache.get(cache_key)
            if entry is None:
                return None, False
            if entry.expires_at <= now:
                del self._cache[cache_key]
                return None, False
            self._cache.move_to_end(cache_key)
            return entry.value, True

    def _set_cached(
        self,
        cache_key: tuple[float, float],
        value: RefugeAddress | None,
        now: float,
    ) -> None:
        with self._cache_lock:
            self._cache[cache_key] = _CacheEntry(now + CACHE_TTL_SECONDS, value)
            self._cache.move_to_end(cache_key)
            while len(self._cache) > CACHE_MAX_ENTRIES:
                self._cache.popitem(last=False)


def _finite_float(value: Any, minimum: float, maximum: float) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or not minimum <= number <= maximum:
        return None
    return number
