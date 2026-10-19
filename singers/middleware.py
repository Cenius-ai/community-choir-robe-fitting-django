"""Response hardening headers.

The app is fully server-rendered with same-origin assets, so a strict
``default-src 'self'`` policy needs no inline-script exemption.
"""


class SecurityHeadersMiddleware:
    CSP = (
        "default-src 'self'; "
        "img-src 'self' data:; "
        "style-src 'self'; "
        "script-src 'self'; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "form-action 'self'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'"
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Content-Security-Policy", self.CSP)
        if request.path.startswith("/admin/"):
            response.headers["Content-Security-Policy"] = self.CSP + "; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'"
        return response
