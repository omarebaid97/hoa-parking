"""Security headers middleware.

This app is meant to be reached only through a Cloudflare tunnel hostname
that isn't linked from anywhere public, but it still shouldn't be indexed
or leak fingerprintable defaults - see CLAUDE.md's public-exposure rules
for the deployment side of this (out of scope for this local build task).
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        # No CDNs / external runtime deps anywhere in this app (map assets,
        # fonts, JS are all copied in under /static) so a strict same-origin
        # CSP doesn't break anything.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self' "
            "'unsafe-inline'; script-src 'self'; frame-ancestors 'none'"
        )
        return response
