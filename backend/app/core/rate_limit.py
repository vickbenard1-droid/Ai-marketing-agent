"""
Rate limiting foundation using slowapi (Redis-backed limiter would be
plugged in here for multi-instance deployments; in-memory is fine for
local dev this week).
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT_DEFAULT])
