"""
Regression test for a real gap found during the Week 12 security audit:
app.state.limiter and the RateLimitExceeded exception handler were both
configured in app/main.py, but SlowAPIMiddleware was never added -
without it, slowapi's global default_limits (app.core.rate_limit.limiter)
never actually applied to any route that didn't carry an explicit
@limiter.limit(...) decorator. That meant every authenticated business
endpoint without an explicit decorator - the large majority of this
app's ~190 routes - had genuinely no rate limiting at all.

Confirmed behaviorally before fixing: with the middleware absent, an
aggressive 3/minute default let 6 rapid real requests to an undecorated
authenticated route all succeed with no 429.

This test builds a MINIMAL, ISOLATED FastAPI app that mirrors the real
app.main.py wiring exactly (same Limiter/SlowAPIMiddleware/exception-
handler pattern), rather than importlib.reload()-ing the real
application modules. An earlier version of this test did reload
app.main/app.core.config/app.core.rate_limit directly to get a fresh
RATE_LIMIT_DEFAULT - that approach was tried, found to corrupt shared
module state for every test that ran afterward in the same process
(12 unrelated tests failed), and was replaced with this fully isolated
version, which leaves the real application's module state completely
untouched.
"""
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address


def test_slowapi_middleware_is_required_for_default_limits_to_apply():
    """
    Isolated proof of the exact mechanism behind the real bug: without
    SlowAPIMiddleware, a Limiter's default_limits do nothing for a route
    with no explicit @limiter.limit(...) decorator, even though
    app.state.limiter and the exception handler are both configured
    correctly - which is precisely the (broken) state app/main.py was in
    before the Week 12 fix.
    """
    limiter = Limiter(key_func=get_remote_address, default_limits=["3/minute"])
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    # Deliberately NOT adding SlowAPIMiddleware here - this reproduces the bug.

    @app.get("/undecorated")
    def undecorated_route():
        return {"ok": True}

    client = TestClient(app)
    statuses = [client.get("/undecorated").status_code for _ in range(6)]
    assert 429 not in statuses, (
        "This asserts the BUGGY behavior on purpose, to prove the middleware is the "
        f"actual mechanism at fault, not something else - got: {statuses}"
    )


def test_slowapi_middleware_makes_default_limits_apply_to_undecorated_routes():
    """The fix, proven in isolation: identical setup, with
    SlowAPIMiddleware added - now the same undecorated route is genuinely
    rate-limited by the global default."""
    limiter = Limiter(key_func=get_remote_address, default_limits=["3/minute"])
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    @app.get("/undecorated")
    def undecorated_route():
        return {"ok": True}

    client = TestClient(app)
    statuses = [client.get("/undecorated").status_code for _ in range(6)]
    assert statuses[:3] == [200, 200, 200], f"Expected the first 3 requests within the limit to succeed, got: {statuses}"
    assert 429 in statuses, f"Expected the global default limit to trigger a 429 within 6 rapid requests at 3/minute, got: {statuses}"


def test_real_app_has_slowapi_middleware_installed():
    """
    The actual regression guard for the real application: imports the
    REAL app.main.app (no reload, no mutation) and inspects its
    middleware stack directly, so this test fails loudly if
    SlowAPIMiddleware is ever removed again - without making any real
    HTTP calls or touching shared module/dependency-override state that
    other test files rely on.
    """
    from app.main import app as real_app

    middleware_classes = {mw.cls.__name__ for mw in real_app.user_middleware}
    assert "SlowAPIMiddleware" in middleware_classes, (
        f"app.main.app is missing SlowAPIMiddleware - its global rate limit default_limits "
        f"will silently do nothing for any route without an explicit @limiter.limit(...) "
        f"decorator. Installed middleware: {middleware_classes}"
    )
