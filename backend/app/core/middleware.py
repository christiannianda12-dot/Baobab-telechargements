"""En-têtes de sécurité et protection CSRF (contrôle d'origine) pour l'authentification par cookie."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import get_settings

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


class OriginCheckMiddleware(BaseHTTPMiddleware):
    """Une requête qui modifie des données et s'appuie sur le cookie de session (sans en-tête Authorization)
    doit provenir d'une origine autorisée. SameSite=Lax est la première barrière, ceci la seconde."""

    async def dispatch(self, request, call_next):
        s = get_settings()
        if (
            request.method in UNSAFE
            and s.session_cookie_name in request.cookies
            and "authorization" not in request.headers
        ):
            origin = request.headers.get("origin")
            if origin is None and (ref := request.headers.get("referer")):
                origin = "/".join(ref.split("/")[:3])
            if origin not in s.cors_origin_list:
                return JSONResponse({"detail": "Origine non autorisée."}, status_code=403)
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        resp = await call_next(request)
        s = get_settings()
        h = resp.headers
        h["X-Content-Type-Options"] = "nosniff"
        h["X-Frame-Options"] = "DENY"
        h["Referrer-Policy"] = "no-referrer"
        h["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.url.path.startswith("/api/"):
            h["Cache-Control"] = "no-store"  # données privées : jamais en cache partagé
        if s.environment == "production":
            h["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            h["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return resp
