from django.core.cache import cache


def allow(key, limit, window_seconds):
    """True if this hit is within `limit` per `window_seconds` for `key`."""
    full = f"rl:{key}"
    if cache.add(full, 1, timeout=window_seconds):
        return limit >= 1
    try:
        count = cache.incr(full)
    except ValueError:  # expired between add and incr
        cache.add(full, 1, timeout=window_seconds)
        return limit >= 1
    return count <= limit
