"""
FastAPI application entrypoint.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.rate_limit import limiter

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="AI marketing employee platform — Week 1 foundation",
    debug=settings.DEBUG,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
# Without this middleware, slowapi's default_limits (the global per-IP
# rate limit configured in app.core.rate_limit) never actually applies to
# any route - only routes carrying an explicit @limiter.limit(...)
# decorator would be limited. Confirmed this behaviorally during the
# Week 12 security audit before adding the fix: with this middleware
# absent, an aggressive 3/minute default let 6 rapid real requests to an
# undecorated authenticated route all succeed with no 429 at all.
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.APP_ENV}
